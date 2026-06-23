#!/usr/bin/env python3
"""Build the unified OOD176 dataset from Old112 and New64 matrix snapshots."""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_ROOT = REPO_ROOT / "data" / "matrices" / "phase2_ood"

OLD112_SOURCE = MATRIX_ROOT / "raw" / "old112" / "matrix.json"
NEW64_JSON_SOURCE = MATRIX_ROOT / "raw" / "new64" / "matrix.json"
NEW64_CSV_SOURCE = MATRIX_ROOT / "raw" / "new64" / "matrix.csv"
NEW64_MD_SOURCE = MATRIX_ROOT / "raw" / "new64" / "matrix.md"
TASKS_SNAPSHOT = MATRIX_ROOT / "unified" / "tasks.jsonl"
TASKS_SNAPSHOT_LABEL = "data/matrices/phase2_ood/unified/tasks.jsonl"
PRICING_PATH = REPO_ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json"

RAW_DIR = MATRIX_ROOT / "raw"
UNIFIED_DIR = MATRIX_ROOT / "unified"
ACROUTER_V2_DIR = MATRIX_ROOT / "acrouter_v2_data"

MODEL_ALIASES_NEW64_TO_ACROUTER = {
    "claude-opus-4-6": "claude-opus-4-6",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "gpt-5.4-medium": "gpt-5.4",
    "glm-5": "glm-5",
    "kimi-k2.6": "kimi-k2.5",
    "MiniMax-M2.5": "MiniMax-M2.7",
    "qwen3.5-plus": "qwen3.5-plus",
    "qwen3.6-plus": "Qwen3-Max",
}

BENCH_TO_DIMENSION = {
    "featurebench": "bug_fixing",
    "longcli": "code_generation",
    "swe_ci": "bug_fixing",
    "old112": "bug_fixing",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def copy_raw_sources() -> None:
    (RAW_DIR / "old112").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "new64").mkdir(parents=True, exist_ok=True)
    for src, dst in [
        (OLD112_SOURCE, RAW_DIR / "old112" / "matrix.json"),
        (NEW64_JSON_SOURCE, RAW_DIR / "new64" / "matrix.json"),
        (NEW64_CSV_SOURCE, RAW_DIR / "new64" / "matrix.csv"),
        (NEW64_MD_SOURCE, RAW_DIR / "new64" / "matrix.md"),
    ]:
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)


def load_pricing() -> dict[str, dict]:
    return read_json(PRICING_PATH)["models"]


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int, pricing: dict[str, dict]) -> float:
    price = pricing[model]
    return round(
        (
            input_tokens * float(price["input_per_1m"])
            + output_tokens * float(price["output_per_1m"])
        )
        / 1_000_000,
        9,
    )


def old_model_means(old: dict) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, int] = defaultdict(int)
    for task_cells in old["matrix"].values():
        for model, cell in task_cells.items():
            counts[model] += 1
            totals[model]["cost_usd"] += float(cell.get("cost_usd", 0.0) or 0.0)
            totals[model]["in_tok"] += float(cell.get("in_tok", 0) or 0)
            totals[model]["out_tok"] += float(cell.get("out_tok", 0) or 0)
            totals[model]["calls"] += float(cell.get("calls", 0) or 0)
    means = {}
    for model, n in counts.items():
        means[model] = {key: value / n for key, value in totals[model].items()}
    return means


def load_new64_task_prompts() -> dict[tuple[str, str], dict]:
    """Load New64 prompts from the bundled OOD176 task snapshot."""
    out = {}
    if not TASKS_SNAPSHOT.exists():
        return out
    with TASKS_SNAPSHOT.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source_split") != "new64":
                continue
            bench = row.get("bench", "")
            original_id = row.get("original_task_id", "")
            prompt = row.get("prompt", "")
            if not original_id or not bench or not prompt:
                continue
            out[(bench, original_id)] = {
                "prompt": prompt,
                "repo": row.get("repo", ""),
                "category": row.get("category", ""),
                "source_task_id": row.get("source_task_id", ""),
            }
    return out


def load_old112_task_prompts() -> dict[str, dict]:
    """Load Old112 prompts from the bundled OOD176 task snapshot."""
    out = {}
    if not TASKS_SNAPSHOT.exists():
        return out
    with TASKS_SNAPSHOT.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source_split") != "old112":
                continue
            original_id = row.get("original_task_id", "")
            prompt = row.get("prompt", "")
            if not original_id or not prompt:
                continue
            out[original_id] = {
                "prompt": prompt,
                "source_task_id": row.get("source_task_id", ""),
                "source_dataset": row.get("source_dataset", ""),
                "language": row.get("language", ""),
                "difficulty": row.get("difficulty", ""),
            }
    return out


def normalize_old112(
    old: dict,
    prompt_rows: dict[str, dict],
    pricing: dict[str, dict],
) -> tuple[list[dict], dict[str, dict]]:
    metadata_rows = []
    matrix = {}
    for original_id in old["ids"]:
        task_id = f"old112::{original_id}"
        prompt_row = prompt_rows.get(original_id, {})
        prompt = prompt_row.get("prompt") or f"SWE-bench Verified OOD task {original_id}"
        metadata_rows.append(
            {
                "task_id": task_id,
                "source_split": "old112",
                "bench": "old112",
                "original_task_id": original_id,
                "dimension": BENCH_TO_DIMENSION["old112"],
                "prompt": prompt,
                "prompt_source": TASKS_SNAPSHOT_LABEL if prompt_row else "fallback_task_id",
                "source_task_id": prompt_row.get("source_task_id", ""),
                "source_dataset": prompt_row.get("source_dataset", "SWE-bench Verified"),
                "language": prompt_row.get("language", "python"),
                "difficulty": prompt_row.get("difficulty", ""),
            }
        )
        matrix[task_id] = {}
        for model in old["models"]:
            cell = dict(old["matrix"][original_id].get(model, {}))
            in_tok = int(cell.get("in_tok", 0) or 0)
            out_tok = int(cell.get("out_tok", 0) or 0)
            matrix[task_id][model] = {
                "resolved": bool(cell.get("resolved")),
                "apply_ok": bool(cell.get("apply_ok")),
                "non_empty": bool(cell.get("non_empty")),
                "graded": bool(cell.get("graded")),
                "in_tok": in_tok,
                "out_tok": out_tok,
                "calls": int(cell.get("calls", 0) or 0),
                "cost_usd": compute_cost_usd(model, in_tok, out_tok, pricing),
                "cost_source": "token_log_pricing",
                "source_split": "old112",
                "source_model": model,
            }
    return metadata_rows, matrix


def fallback_cell(
    status: str,
    model: str,
    means: dict[str, dict[str, float]],
    source_model: str,
    pricing: dict[str, dict],
) -> dict:
    mean = means.get(model, {})
    ran = status in {"pass", "fail"}
    in_tok = int(round(mean.get("in_tok", 0.0)))
    out_tok = int(round(mean.get("out_tok", 0.0)))
    return {
        "resolved": status == "pass",
        "apply_ok": ran,
        "non_empty": ran,
        "graded": ran,
        "in_tok": in_tok,
        "out_tok": out_tok,
        "calls": int(round(mean.get("calls", 0.0))),
        "cost_usd": compute_cost_usd(model, in_tok, out_tok, pricing),
        "cost_source": "token_log_pricing",
        "source_split": "new64",
        "source_model": source_model,
        "source_status": status,
        "cost_token_source": "old112_model_mean_fallback",
    }


def normalize_new64(
    new64: dict,
    models: list[str],
    means: dict[str, dict[str, float]],
    prompt_rows: dict[tuple[str, str], dict],
    pricing: dict[str, dict],
) -> tuple[list[dict], dict[str, dict]]:
    metadata_rows = []
    matrix = {}
    for row in new64["matrix_rows"]:
        bench = row["bench"]
        original_id = row["task_id"]
        task_id = f"new64::{bench}::{original_id}"
        prompt_row = prompt_rows.get((bench, original_id), {})
        prompt = prompt_row.get("prompt") or f"New64 {bench} task {original_id}"
        metadata_rows.append(
            {
                "task_id": task_id,
                "source_split": "new64",
                "bench": bench,
                "original_task_id": original_id,
                "dimension": BENCH_TO_DIMENSION.get(bench, "bug_fixing"),
                "prompt": prompt,
                "prompt_source": TASKS_SNAPSHOT_LABEL if prompt_row else "fallback_task_id",
                "source_task_id": prompt_row.get("source_task_id", ""),
                "repo": prompt_row.get("repo", ""),
                "category": prompt_row.get("category", ""),
            }
        )
        matrix[task_id] = {}
        for source_model, canonical_model in MODEL_ALIASES_NEW64_TO_ACROUTER.items():
            if canonical_model not in models:
                raise KeyError(f"canonical model {canonical_model!r} is not in Old112 model list")
            status = str(row.get(source_model, "missing"))
            matrix[task_id][canonical_model] = fallback_cell(
                status=status,
                model=canonical_model,
                means=means,
                source_model=source_model,
                pricing=pricing,
            )
    return metadata_rows, matrix


def to_acrouter_v2_obs(matrix: dict[str, dict]) -> dict[str, dict]:
    obs = {}
    for task_id, cells in matrix.items():
        obs[task_id] = {}
        for model, cell in cells.items():
            obs[task_id][model] = {
                "perf": 1.0 if cell.get("resolved") else 0.0,
                "cost": float(cell.get("cost_usd", 0.0) or 0.0),
                "tokens": int(cell.get("in_tok", 0) or 0) + int(cell.get("out_tok", 0) or 0),
                "latency_ms": 0,
            }
    return obs


def write_processed_tasks(metadata_rows: list[dict]) -> None:
    processed_dir = ACROUTER_V2_DIR / "processed"
    if processed_dir.exists():
        shutil.rmtree(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    by_dim: dict[str, list[dict]] = defaultdict(list)
    for row in metadata_rows:
        by_dim[row["dimension"]].append(row)
    for dim, rows in sorted(by_dim.items()):
        path = processed_dir / f"{dim}.jsonl"
        with path.open("w") as fh:
            for row in rows:
                fh.write(
                    json.dumps(
                        {
                            "task_id": row["task_id"],
                            "dimension": row["dimension"],
                            "source_dataset": row["source_split"],
                            "prompt": row["prompt"],
                            "language": "python",
                            "difficulty": "medium",
                            "test_cases": "",
                            "metadata": {
                                "bench": row["bench"],
                                "original_task_id": row["original_task_id"],
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )


def write_normalized_csv(metadata_rows: list[dict], matrix: dict[str, dict], models: list[str]) -> None:
    path = UNIFIED_DIR / "results_long.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_by_id = {row["task_id"]: row for row in metadata_rows}
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "task_id",
                "source_split",
                "bench",
                "original_task_id",
                "dimension",
                "model",
                "source_model",
                "resolved",
                "apply_ok",
                "graded",
                "in_tok",
                "out_tok",
                "calls",
                "cost_usd",
                "source_status",
            ],
        )
        writer.writeheader()
        for task_id in sorted(matrix):
            meta = meta_by_id[task_id]
            for model in models:
                cell = matrix[task_id][model]
                writer.writerow(
                    {
                        "task_id": task_id,
                        "source_split": meta["source_split"],
                        "bench": meta["bench"],
                        "original_task_id": meta["original_task_id"],
                        "dimension": meta["dimension"],
                        "model": model,
                        "source_model": cell.get("source_model", model),
                        "resolved": int(bool(cell.get("resolved"))),
                        "apply_ok": int(bool(cell.get("apply_ok"))),
                        "graded": int(bool(cell.get("graded"))),
                        "in_tok": int(cell.get("in_tok", 0) or 0),
                        "out_tok": int(cell.get("out_tok", 0) or 0),
                        "calls": int(cell.get("calls", 0) or 0),
                        "cost_usd": float(cell.get("cost_usd", 0.0) or 0.0),
                        "source_status": cell.get("source_status", ""),
                    }
                )


def write_readme(summary: dict) -> None:
    lines = [
        "# OOD Dataset",
        "",
        "Unified OOD176 bundle for router testing.",
        "",
        "## Layout",
        "",
        "- `raw/old112/matrix.json`: original Old112 ACRouter OOD matrix.",
        "- `raw/new64/matrix.{json,csv,md}`: original New64 comparable matrix snapshot.",
        "- `unified/matrix_acrouter_ood176.json`: ACRouter release-compatible 176-task matrix.",
        "- `unified/acrouter_v2_obs_matrix.json`: `acrouter_v2` observation matrix.",
        "- `unified/tasks.jsonl`: task metadata for all 176 rows.",
        "- `unified/results_long.csv`: normalized long-form per-task/per-model table.",
        "- `acrouter_v2_data/processed/*.jsonl`: processed task files loadable by `acrouter_v2.data_utils.load_tasks`.",
        "- `scripts/run_acrouter_ood176.py`: one-command ACRouter OOD176 entrypoint.",
        "- `scripts/run_baselines_ood176.py`: one-command replay for the main-table OOD baselines on the 176-task matrix.",
        "",
        "## Model Mapping",
        "",
        "Old112 already uses the ACRouter release model names. New64 raw model names are mapped as follows:",
        "",
        "| New64 model | ACRouter canonical model |",
        "| --- | --- |",
    ]
    for source, target in MODEL_ALIASES_NEW64_TO_ACROUTER.items():
        lines.append(f"| `{source}` | `{target}` |")
    lines.extend(
        [
            "",
            "New64 status cells preserve the original model name in `source_model`; token and cost fields use",
            "Old112 per-model means as fallback values because the New64 matrix snapshot is pass/fail only.",
            "",
            "## Summary",
            "",
            f"- Generated: {summary['generated_utc']}",
            f"- Old112 tasks: {summary['old112_n']}",
            f"- Old112 tasks with real prompts: {summary.get('old112_real_prompt_n', 0)}",
            f"- Old112 prompt source: `{summary.get('old112_prompt_source', '')}`",
            f"- New64 tasks: {summary['new64_n']}",
            f"- New64 tasks with real prompts: {summary.get('new64_real_prompt_n', 0)}",
            f"- New64 prompt source: `{summary.get('new64_prompt_source', '')}`",
            f"- Combined tasks: {summary['combined_n']}",
            f"- Models: {', '.join(f'`{m}`' for m in summary['models'])}",
            "",
            "Run:",
            "",
            "```bash",
            "python scripts/run_acrouter_ood176.py",
            "python scripts/run_baselines_ood176.py",
            "```",
            "",
            "Baseline outputs are written to `outputs/baselines_ood176/`:",
            "",
            "- `baseline_table.{md,csv,tex}`: main table with in-distribution columns kept unchanged and OOD columns recomputed at `n=176`.",
            "- `baseline_metrics.{json,csv}`: full metric payloads and decision-source notes.",
            "- `decisions/*.jsonl`: per-task decisions for each applicable baseline.",
            "",
            "For trained-policy baselines where only published OOD112 decisions are available in this worktree,",
            "the Old112 portion is replayed from those decisions. When a saved router is available, the New64",
            "portion is predicted from the task prompt; otherwise it uses a documented modal extension from the",
            "Old112 decisions. The output notes record the exact source file and extension/prediction path.",
        ]
    )
    (MATRIX_ROOT / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    copy_raw_sources()
    old = read_json(OLD112_SOURCE)
    new64 = read_json(NEW64_JSON_SOURCE)
    models = list(old["models"])
    pricing = load_pricing()
    means = old_model_means(old)
    old_prompt_rows = load_old112_task_prompts()
    new_prompt_rows = load_new64_task_prompts()

    old_meta, old_matrix = normalize_old112(old, old_prompt_rows, pricing)
    new_meta, new_matrix = normalize_new64(new64, models, means, new_prompt_rows, pricing)
    metadata_rows = old_meta + new_meta
    matrix = {**old_matrix, **new_matrix}
    ids = [row["task_id"] for row in metadata_rows]

    if len(ids) != 176:
        raise RuntimeError(f"expected 176 combined tasks, got {len(ids)}")
    if len(set(ids)) != len(ids):
        raise RuntimeError("combined task ids are not unique")
    for task_id, cells in matrix.items():
        missing = set(models) - set(cells)
        if missing:
            raise RuntimeError(f"{task_id} missing model cells: {sorted(missing)}")

    summary = {
        "generated_utc": now_utc(),
        "old112_n": len(old_meta),
        "old112_prompt_source": TASKS_SNAPSHOT_LABEL,
        "old112_real_prompt_n": sum(1 for row in old_meta if row.get("prompt_source") != "fallback_task_id"),
        "new64_n": len(new_meta),
        "combined_n": len(ids),
        "models": models,
        "new64_model_aliases": MODEL_ALIASES_NEW64_TO_ACROUTER,
        "new64_prompt_source": TASKS_SNAPSHOT_LABEL,
        "new64_real_prompt_n": sum(1 for row in new_meta if row.get("prompt_source") != "fallback_task_id"),
    }

    write_json(
        UNIFIED_DIR / "matrix_acrouter_ood176.json",
        {
            "ids": ids,
            "models": models,
            "matrix": matrix,
            "metadata": {row["task_id"]: row for row in metadata_rows},
            "summary": summary,
        },
    )
    write_json(UNIFIED_DIR / "acrouter_v2_obs_matrix.json", to_acrouter_v2_obs(matrix))
    with (UNIFIED_DIR / "tasks.jsonl").open("w") as fh:
        for row in metadata_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_normalized_csv(metadata_rows, matrix, models)
    write_processed_tasks(metadata_rows)
    write_json(UNIFIED_DIR / "summary.json", summary)
    write_readme(summary)

    print(f"wrote {(UNIFIED_DIR / 'matrix_acrouter_ood176.json').relative_to(REPO_ROOT)}")
    print(f"wrote {(UNIFIED_DIR / 'acrouter_v2_obs_matrix.json').relative_to(REPO_ROOT)}")
    print(f"combined_n={len(ids)} models={len(models)}")


if __name__ == "__main__":
    main()
