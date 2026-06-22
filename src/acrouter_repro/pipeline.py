"""Config-driven evaluation pipeline for custom models and benchmark tasks."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .ood_repro import OODData, score_ood, verify_and_escalate


def run_pipeline(config_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Run a custom ACRouter evaluation pipeline from a JSON config."""

    config_path = config_path.resolve()
    base_dir = config_path.parent
    config = read_json(config_path)
    out_dir = _resolve_path(base_dir, output_dir or config.get("output_dir") or "outputs/custom_pipeline")
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = _prepare_matrix(config, base_dir, out_dir)
    data = OODData(matrix_path)
    evaluations = config.get("evaluations") or [config.get("router", {"type": "verify_and_escalate"})]

    summary_rows = []
    results: dict[str, Any] = {
        "config": _display_path(config_path),
        "matrix": _display_path(matrix_path),
        "evaluations": {},
    }
    for spec in evaluations:
        rows = _run_router_spec(data, spec)
        name = _router_name(spec)
        metrics = score_ood(data, rows)
        safe_name = _safe_name(name)
        write_jsonl(out_dir / "decisions" / f"{safe_name}.jsonl", rows)
        write_json(out_dir / "metrics" / f"{safe_name}.json", metrics)
        summary_rows.append({"router": name, **metrics})
        results["evaluations"][name] = {"metrics": metrics, "decisions": rows}

    _write_summary_csv(out_dir / "summary.csv", summary_rows)
    _write_summary_md(out_dir / "summary.md", summary_rows)
    write_json(out_dir / "resolved_config.json", {**config, "_matrix_path": _display_path(matrix_path, out_dir)})
    write_json(out_dir / "results.json", {"matrix": _display_path(matrix_path, out_dir), "summary": summary_rows})
    return {"output_dir": out_dir, "matrix": matrix_path, "summary": summary_rows, "results": results}


def _prepare_matrix(config: dict[str, Any], base_dir: Path, out_dir: Path) -> Path:
    if config.get("matrix_path"):
        matrix_path = _resolve_path(base_dir, config["matrix_path"])
        _validate_matrix(read_json(matrix_path), config)
        return matrix_path

    tasks_path = config.get("tasks_path")
    results_path = config.get("results_path")
    if not tasks_path or not results_path:
        raise ValueError("config must provide either matrix_path or both tasks_path and results_path")

    tasks = list(read_jsonl(_resolve_path(base_dir, tasks_path)))
    results = list(read_jsonl(_resolve_path(base_dir, results_path)))
    matrix = build_matrix(tasks, results, config)
    _validate_matrix(matrix, config)
    matrix_path = out_dir / "matrix.json"
    write_json(matrix_path, matrix)
    return matrix_path


def build_matrix(tasks: list[dict[str, Any]], results: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical matrix format from task and model-result JSONL rows."""

    task_ids = [_task_id(task) for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("tasks_path contains duplicate task ids")

    model_order = _model_order(config, results)
    score_threshold = float(config.get("score_threshold", 1.0))
    matrix = {task_id: {} for task_id in task_ids}

    for row in results:
        task_id = _task_id(row)
        model = str(row.get("model") or row.get("model_id") or "")
        if not task_id or not model:
            raise ValueError("each result row must include task_id and model")
        if task_id not in matrix:
            raise ValueError(f"result row references unknown task_id: {task_id}")
        if model in matrix[task_id]:
            raise ValueError(f"duplicate result row for task/model: {task_id}/{model}")
        if model not in model_order:
            model_order.append(model)

        in_tok = int(row.get("in_tok", row.get("input_tokens", 0)) or 0)
        out_tok = int(row.get("out_tok", row.get("output_tokens", 0)) or 0)
        score = row.get("score")
        resolved = _bool_value(row.get("resolved"))
        if resolved is None and score is not None:
            resolved = float(score) >= score_threshold
        if resolved is None:
            resolved = False
        apply_ok = _bool_value(row.get("apply_ok"))
        if apply_ok is None:
            apply_ok = resolved
        cost = row.get("cost_usd")
        if cost is None:
            cost = _cost_from_pricing(model, in_tok, out_tok, config.get("models", {}))

        cell = {
            "resolved": bool(resolved),
            "apply_ok": bool(apply_ok),
            "non_empty": bool(row.get("non_empty", True)),
            "graded": bool(row.get("graded", True)),
            "in_tok": in_tok,
            "out_tok": out_tok,
            "cost_usd": round(float(cost or 0.0), 8),
        }
        if score is not None:
            cell["score"] = float(score)
        matrix[task_id][model] = cell

    return {
        "ids": task_ids,
        "models": model_order,
        "matrix": matrix,
        "metadata": {
            "name": config.get("name", "custom_pipeline"),
            "source": "acrouter_custom_pipeline",
            "n_tasks": len(task_ids),
            "n_models": len(model_order),
        },
    }


def _run_router_spec(data: OODData, spec: dict[str, Any]) -> list[dict[str, Any]]:
    router_type = spec.get("type", "verify_and_escalate")
    if router_type in {"verify_and_escalate", "acrouter"}:
        chain = list(spec.get("cheap_chain") or data.models[: min(4, len(data.models))])
        escalate_to = spec.get("escalate_to") or (data.models[-1] if data.models else None)
        if not escalate_to:
            raise ValueError("verify_and_escalate requires at least one model")
        if escalate_to in chain:
            raise ValueError("verify_and_escalate escalate_to must not also appear in cheap_chain")
        _require_models(data, chain + [escalate_to])
        return verify_and_escalate(data, k=int(spec.get("k", 2)), cheap_chain=chain, escalate_to=escalate_to)
    if router_type == "always":
        model = spec.get("model")
        if not model:
            raise ValueError("always router requires a model")
        _require_models(data, [model])
        return [_single_model_row(data, task_id, model) for task_id in data.ids]
    if router_type == "oracle":
        return [_single_model_row(data, task_id, data.reward_oracle_model[task_id]) for task_id in data.ids]
    if router_type == "cheapest":
        rows = []
        for task_id in data.ids:
            model = min(data.models, key=lambda m: data.cost(task_id, m))
            rows.append(_single_model_row(data, task_id, model))
        return rows
    raise ValueError(f"unsupported router type: {router_type}")


def _single_model_row(data: OODData, task_id: str, model: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "chosen_model": model,
        "chain_run": [model],
        "resolved": bool(data.resolved(task_id, model)),
        "apply_ok": bool(data.apply_ok(task_id, model)),
        "cost_usd": round(data.cost(task_id, model), 6),
        "escalated": False,
        "n_steps": 1,
    }


def _validate_matrix(matrix: dict[str, Any], config: dict[str, Any]) -> None:
    required = {"ids", "models", "matrix"}
    missing = required - set(matrix)
    if missing:
        raise ValueError(f"matrix is missing keys: {sorted(missing)}")
    ids = matrix["ids"]
    models = matrix["models"]
    if not ids:
        raise ValueError("matrix must contain at least one task id")
    if not models:
        raise ValueError("matrix must contain at least one model")
    if len(set(ids)) != len(ids):
        raise ValueError("matrix contains duplicate task ids")
    if len(set(models)) != len(models):
        raise ValueError("matrix contains duplicate models")
    if config.get("allow_missing_cells", False):
        return
    for task_id in ids:
        cells = matrix["matrix"].get(task_id, {})
        missing_models = [model for model in models if model not in cells]
        if missing_models:
            raise ValueError(f"task {task_id} is missing model cells: {missing_models}")


def _require_models(data: OODData, models: list[str]) -> None:
    missing = [model for model in models if model not in data.models]
    if missing:
        raise ValueError(f"router references models not present in matrix: {missing}")


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["router", "n", "AvgPerf%", "CumReg", "$Total", "Perf/$", "Apply_ok%", "rAcc_reward_oracle"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_summary_md(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Custom ACRouter Pipeline Summary",
        "",
        "| router | n | AvgPerf% | CumReg | $Total | Perf/$ | Apply_ok% | rAcc |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {router} | {n} | {avg:.2f} | {reg:.1f} | {cost:.2f} | {perf:.2f} | {apply:.2f} | {racc:.4f} |".format(
                router=row["router"],
                n=row["n"],
                avg=row["AvgPerf%"],
                reg=row["CumReg"],
                cost=row["$Total"],
                perf=row["Perf/$"],
                apply=row["Apply_ok%"],
                racc=row["rAcc_reward_oracle"],
            )
        )
    path.write_text("\n".join(lines) + "\n")


def _model_order(config: dict[str, Any], results: list[dict[str, Any]]) -> list[str]:
    models = config.get("models", {})
    if isinstance(models, dict):
        order = list(models)
    elif isinstance(models, list):
        order = [str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in models]
    else:
        order = []
    for row in results:
        model = str(row.get("model") or row.get("model_id") or "")
        if model and model not in order:
            order.append(model)
    return order


def _cost_from_pricing(model: str, in_tok: int, out_tok: int, models_config: dict[str, Any] | list[Any]) -> float:
    if isinstance(models_config, list):
        pricing = {}
        for item in models_config:
            if isinstance(item, dict) and "name" in item:
                pricing[item["name"]] = item
    else:
        pricing = models_config
    model_cfg = pricing.get(model, {}) if isinstance(pricing, dict) else {}
    input_price = float(model_cfg.get("input_per_1m", model_cfg.get("input_per_million", 0.0)) or 0.0)
    output_price = float(model_cfg.get("output_per_1m", model_cfg.get("output_per_million", 0.0)) or 0.0)
    return in_tok * input_price / 1_000_000 + out_tok * output_price / 1_000_000


def _resolve_path(base_dir: Path, path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _display_path(path: Path, base_dir: Path | None = None) -> str:
    base = (base_dir or Path.cwd()).resolve()
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(base))
    except ValueError:
        return str(path)


def _task_id(row: dict[str, Any]) -> str:
    task_id = row.get("task_id", row.get("id"))
    if not task_id:
        raise ValueError("row is missing task_id or id")
    return str(task_id)


def _bool_value(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "passed", "resolved"}:
            return True
        if lowered in {"0", "false", "no", "n", "failed", "unresolved"}:
            return False
    raise ValueError(f"cannot parse boolean value: {value!r}")


def _router_name(spec: dict[str, Any]) -> str:
    if spec.get("name"):
        return str(spec["name"])
    if spec.get("type") == "always":
        return f"always_{spec.get('model', 'unknown')}"
    return str(spec.get("type", "verify_and_escalate"))


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "router"
