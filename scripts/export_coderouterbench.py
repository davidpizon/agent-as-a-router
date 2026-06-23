#!/usr/bin/env python3
"""Export CodeRouterBench as user-facing task-by-model tables."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "coderouterbench"

ID_OBS_MATRIX = ROOT / "data" / "matrices" / "phase1_acrouter_v2" / "obs_matrix_clean.json"
ID_TASK_DIMENSIONS = ROOT / "data" / "id" / "task_dimensions.jsonl"
ID_TOKENS = ROOT / "data" / "id" / "tokens.jsonl"
ID_SPLIT_DIR = ROOT / "data" / "id" / "splits"
PRICING_PATH = ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json"

OOD_MATRIX = ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "matrix_acrouter_ood176.json"
OOD_RESULTS_LONG = ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "results_long.csv"
OOD_TASKS = ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "tasks.jsonl"

CANONICAL_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "gpt-5.4",
    "glm-5",
    "kimi-k2.5",
    "MiniMax-M2.7",
    "Qwen3-Max",
    "qwen3.5-plus",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_id_splits() -> dict[str, str]:
    split_by_task = {}
    for split in ["train", "val", "test"]:
        for task_id in read_json(ID_SPLIT_DIR / f"{split}.json"):
            split_by_task[task_id] = split
    return split_by_task


def load_id_dimensions() -> dict[str, str]:
    return {
        row["task_id"]: row.get("dimension", "")
        for row in read_jsonl(ID_TASK_DIMENSIONS)
    }


def load_id_tokens() -> dict[tuple[str, str], dict[str, int]]:
    tokens = {}
    for row in read_jsonl(ID_TOKENS):
        tokens[(row["task_id"], row["model"])] = {
            "input_tokens": int(row.get("input_tokens", 0) or 0),
            "output_tokens": int(row.get("output_tokens", 0) or 0),
        }
    return tokens


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int, pricing: dict[str, Any]) -> float:
    price = pricing[model]
    cost = (
        input_tokens * float(price["input_per_1m"])
        + output_tokens * float(price["output_per_1m"])
    ) / 1_000_000
    return round(cost, 9)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_id_tables(output_dir: Path) -> dict[str, Any]:
    obs_matrix: dict[str, dict[str, dict[str, Any]]] = read_json(ID_OBS_MATRIX)
    split_by_task = load_id_splits()
    dimension_by_task = load_id_dimensions()
    token_by_task_model = load_id_tokens()
    pricing = read_json(PRICING_PATH)["models"]

    observed_models = {model for row in obs_matrix.values() for model in row}
    if set(CANONICAL_MODELS) != observed_models:
        raise ValueError(f"Unexpected ID model set: {sorted(observed_models)}")

    fieldnames = [
        "task_id",
        "split",
        "source_split",
        "dimension",
        "model",
        "score",
        "cost_usd",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_ms",
        "cost_source",
    ]

    missing_cells = 0
    missing_token_records = 0
    result_rows = []
    for task_id, model_cells in obs_matrix.items():
        source_split = split_by_task.get(task_id, "")
        public_split = "id_test" if source_split == "test" else "probing"
        for model in CANONICAL_MODELS:
            cell = model_cells.get(model)
            if cell is None:
                missing_cells += 1
                continue
            token_row = token_by_task_model.get((task_id, model))
            if token_row is None:
                missing_token_records += 1
                total_tokens = int(cell.get("tokens", 0) or 0)
                if total_tokens == 0:
                    input_tokens = 0
                    output_tokens = 0
                    cost_usd = 0.0
                    cost_source = "missing_token_record_zero_total"
                else:
                    input_tokens = ""
                    output_tokens = ""
                    cost_usd = ""
                    cost_source = "missing_token_record"
            else:
                input_tokens = token_row["input_tokens"]
                output_tokens = token_row["output_tokens"]
                total_tokens = input_tokens + output_tokens
                cost_usd = compute_cost_usd(model, input_tokens, output_tokens, pricing)
                cost_source = "token_log_pricing"
            result_rows.append(
                {
                    "task_id": task_id,
                    "split": public_split,
                    "source_split": source_split,
                    "dimension": dimension_by_task.get(task_id, ""),
                    "model": model,
                    "score": cell.get("perf", ""),
                    "cost_usd": cost_usd,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "latency_ms": cell.get("latency_ms", ""),
                    "cost_source": cost_source,
                }
            )

    write_csv(output_dir / "id_results_long.csv", fieldnames, result_rows)

    task_rows = [
        {
            "task_id": task_id,
            "split": "id_test" if split_by_task.get(task_id, "") == "test" else "probing",
            "source_split": split_by_task.get(task_id, ""),
            "dimension": dimension_by_task.get(task_id, ""),
        }
        for task_id in obs_matrix
    ]
    write_jsonl(output_dir / "id_tasks.jsonl", task_rows)

    split_summaries = {}
    for obsolete in [
        "id_train_results_long.csv",
        "id_train_tasks.jsonl",
        "id_val_results_long.csv",
        "id_val_tasks.jsonl",
        "id_trainval_results_long.csv",
        "id_trainval_tasks.jsonl",
        "id_id_test_results_long.csv",
        "id_id_test_tasks.jsonl",
    ]:
        (output_dir / obsolete).unlink(missing_ok=True)

    split_files = {
        "probing": ("id_probing_results_long.csv", "id_probing_tasks.jsonl"),
        "id_test": ("id_test_results_long.csv", "id_test_tasks.jsonl"),
    }
    for split, (results_file, tasks_file) in split_files.items():
        split_results = [row for row in result_rows if row["split"] == split]
        split_tasks = [row for row in task_rows if row["split"] == split]
        write_csv(output_dir / results_file, fieldnames, split_results)
        write_jsonl(output_dir / tasks_file, split_tasks)
        split_summaries[split] = {
            "tasks": len(split_tasks),
            "rows": len(split_results),
            "cost_usd_total": round(
                sum(float(row["cost_usd"] or 0.0) for row in split_results), 6
            ),
            "missing_token_records": sum(
                1 for row in split_results if row["cost_source"].startswith("missing_token_record")
            ),
            "source_splits": sorted({row["source_split"] for row in split_results}),
        }

    return {
        "tasks": len(obs_matrix),
        "models": len(CANONICAL_MODELS),
        "rows": len(result_rows),
        "missing_cells": missing_cells,
        "cost_usd_total": round(sum(float(row["cost_usd"] or 0.0) for row in result_rows), 6),
        "missing_token_records": missing_token_records,
        "cost_source": "computed from data/id/tokens.jsonl and data/matrices/phase1_id/model_pricing.json",
        "splits": split_summaries,
        "source_matrix": "data/matrices/phase1_acrouter_v2/obs_matrix_clean.json",
    }


def export_ood_tables(output_dir: Path) -> dict[str, Any]:
    matrix = read_json(OOD_MATRIX)
    if matrix["models"] != CANONICAL_MODELS:
        raise ValueError(f"Unexpected OOD model order: {matrix['models']}")
    pricing = read_json(PRICING_PATH)["models"]

    missing_cells = 0
    for task_id in matrix["ids"]:
        model_cells = matrix["matrix"][task_id]
        for model in CANONICAL_MODELS:
            if model not in model_cells:
                missing_cells += 1

    with OOD_RESULTS_LONG.open(newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if "cost_source" not in fieldnames:
        fieldnames.append("cost_source")
    for row in rows:
        input_tokens = int(row.get("in_tok") or 0)
        output_tokens = int(row.get("out_tok") or 0)
        row["cost_usd"] = compute_cost_usd(row["model"], input_tokens, output_tokens, pricing)
        row["cost_source"] = "token_log_pricing"
    write_csv(output_dir / "ood176_results_long.csv", fieldnames, rows)
    shutil.copy2(OOD_TASKS, output_dir / "ood176_tasks.jsonl")

    return {
        "tasks": len(matrix["ids"]),
        "models": len(CANONICAL_MODELS),
        "rows": len(matrix["ids"]) * len(CANONICAL_MODELS) - missing_cells,
        "missing_cells": missing_cells,
        "cost_usd_total": round(sum(float(row["cost_usd"] or 0.0) for row in rows), 6),
        "cost_source": "computed from in_tok/out_tok and data/matrices/phase1_id/model_pricing.json",
        "source_matrix": "data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json",
    }


def export_models(output_dir: Path) -> list[dict[str, Any]]:
    pricing = read_json(PRICING_PATH)["models"]
    rows = []
    for model in CANONICAL_MODELS:
        row = {"model": model}
        row.update(pricing[model])
        rows.append(row)
    write_json(output_dir / "models.json", {"models": rows})
    return rows


def write_dataset_card(output_dir: Path, summary: dict[str, Any]) -> None:
    text = f"""---
pretty_name: CodeRouterBench
task_categories:
  - text-generation
language:
  - en
license: mit
tags:
  - code
  - benchmark
  - model-routing
  - tabular
  - arxiv:2606.22902
configs:
  - config_name: default
    data_files:
      - split: probing
        path: id_probing_results_long.csv
      - split: id_test
        path: id_test_results_long.csv
      - split: ood176
        path: ood176_results_long.csv
  - config_name: id_full
    data_files:
      - split: all
        path: id_results_long.csv
  - config_name: task_metadata
    data_files:
      - split: id_all
        path: id_tasks.jsonl
      - split: probing
        path: id_probing_tasks.jsonl
      - split: id_test
        path: id_test_tasks.jsonl
      - split: ood176
        path: ood176_tasks.jsonl
---

# CodeRouterBench

CodeRouterBench is the benchmark data released with Agent-as-a-Router. The
core unit is a complete task-by-model result matrix: every benchmark task has
one recorded result for each of the eight canonical backend models.

Repository: [https://github.com/LanceZPF/agent-as-a-router](https://github.com/LanceZPF/agent-as-a-router)

## Associated Paper

- Hugging Face Daily Papers: [Agent-as-a-Router: Agentic Model Routing for Coding Tasks](https://huggingface.co/papers/2606.22902)
- arXiv: [2606.22902](https://arxiv.org/abs/2606.22902)

## Canonical Files

- `id_results_long.csv`: {summary["id"]["tasks"]:,} in-distribution tasks x 8 models = {summary["id"]["rows"]:,} result rows.
- `id_probing_results_long.csv`: {summary["id"]["splits"]["probing"]["tasks"]:,} probing tasks x 8 models = {summary["id"]["splits"]["probing"]["rows"]:,} result rows. This is the merged original train + validation set.
- `id_test_results_long.csv`: {summary["id"]["splits"]["id_test"]["tasks"]:,} ID test tasks x 8 models = {summary["id"]["splits"]["id_test"]["rows"]:,} result rows.
- `ood176_results_long.csv`: 176 OOD tasks x 8 models = {summary["ood176"]["rows"]:,} result rows.
- `id_tasks.jsonl`: ID task metadata with split and dimension.
- `id_probing_tasks.jsonl` and `id_test_tasks.jsonl`: split-specific ID task metadata.
- `ood176_tasks.jsonl`: OOD176 task prompts and metadata.
- `models.json`: canonical model list and USD pricing metadata.
- `summary.json`: counts, source paths, and integrity checks.

Router outputs, baseline decisions, and paper tables are derived artifacts. The
benchmark itself is defined by the task tables above plus the per-model result
rows.

For ID rows, `cost_usd` is computed from `data/id/tokens.jsonl` and
`data/matrices/phase1_id/model_pricing.json`. Rows without a token record leave
`cost_usd`, `input_tokens`, and `output_tokens` blank unless the compact log
records zero total tokens; zero-token rows use
`cost_source=missing_token_record_zero_total`. The current export has
{summary["id"]["missing_token_records"]:,} such legacy rows and
{summary["id"]["cost_usd_total"]:.6f} USD of computed ID cost.

For OOD176 rows, `cost_usd` is recomputed from `in_tok`, `out_tok`, and the same
pricing table. The current export has {summary["ood176"]["cost_usd_total"]:.6f}
USD of computed OOD176 cost.

## Schemas

`id_results_long.csv` columns:

- `task_id`
- `split`: `probing` or `id_test`
- `source_split`: original internal split, one of `train`, `val`, or `test`
- `dimension`
- `model`
- `score`: task score/performance used by the routing oracle
- `cost_usd`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `latency_ms`
- `cost_source`: `token_log_pricing`, `missing_token_record`, or `missing_token_record_zero_total`

`ood176_results_long.csv` columns:

- `task_id`
- `source_split`: `old112` or `new64`
- `bench`
- `original_task_id`
- `dimension`
- `model`
- `resolved`
- `apply_ok`
- `graded`
- `in_tok`
- `out_tok`
- `calls`
- `cost_usd`
- `cost_source`
- `source_status`

## Splits

The current public OOD benchmark is OOD176. The older OOD112/SWE-MiniSandbox
data is retained in the repository only as a legacy supplement.

## Source Matrices

The long-form tables are exported from the nested matrices kept in the GitHub
repository:

- `{summary["id"]["source_matrix"]}`
- `{summary["ood176"]["source_matrix"]}`
"""
    (output_dir / "README.md").write_text(text)


def export(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    id_summary = export_id_tables(output_dir)
    ood_summary = export_ood_tables(output_dir)
    models = export_models(output_dir)
    summary = {
        "dataset": "CodeRouterBench",
        "definition": "complete task-by-model result matrices for eight backend models",
        "models": [row["model"] for row in models],
        "id": id_summary,
        "ood176": ood_summary,
    }
    write_json(output_dir / "summary.json", summary)
    write_dataset_card(output_dir, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = export(args.output_dir)
    print(
        "CodeRouterBench exported: "
        f"ID {summary['id']['tasks']}x{summary['id']['models']} "
        f"+ OOD176 {summary['ood176']['tasks']}x{summary['ood176']['models']} "
        f"to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
