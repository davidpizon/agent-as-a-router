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

    observed_models = {model for row in obs_matrix.values() for model in row}
    if set(CANONICAL_MODELS) != observed_models:
        raise ValueError(f"Unexpected ID model set: {sorted(observed_models)}")

    fieldnames = [
        "task_id",
        "split",
        "dimension",
        "model",
        "score",
        "cost_usd",
        "total_tokens",
        "latency_ms",
    ]

    missing_cells = 0
    result_rows = []
    for task_id, model_cells in obs_matrix.items():
        for model in CANONICAL_MODELS:
            cell = model_cells.get(model)
            if cell is None:
                missing_cells += 1
                continue
            result_rows.append(
                {
                    "task_id": task_id,
                    "split": split_by_task.get(task_id, ""),
                    "dimension": dimension_by_task.get(task_id, ""),
                    "model": model,
                    "score": cell.get("perf", ""),
                    "cost_usd": cell.get("cost", ""),
                    "total_tokens": cell.get("tokens", ""),
                    "latency_ms": cell.get("latency_ms", ""),
                }
            )

    write_csv(output_dir / "id_results_long.csv", fieldnames, result_rows)

    task_rows = [
        {
            "task_id": task_id,
            "split": split_by_task.get(task_id, ""),
            "dimension": dimension_by_task.get(task_id, ""),
        }
        for task_id in obs_matrix
    ]
    write_jsonl(output_dir / "id_tasks.jsonl", task_rows)

    split_summaries = {}
    for split in ["train", "val", "test"]:
        split_results = [row for row in result_rows if row["split"] == split]
        split_tasks = [row for row in task_rows if row["split"] == split]
        write_csv(output_dir / f"id_{split}_results_long.csv", fieldnames, split_results)
        write_jsonl(output_dir / f"id_{split}_tasks.jsonl", split_tasks)
        split_summaries[split] = {
            "tasks": len(split_tasks),
            "rows": len(split_results),
        }

    trainval_results = [row for row in result_rows if row["split"] in {"train", "val"}]
    trainval_tasks = [row for row in task_rows if row["split"] in {"train", "val"}]
    write_csv(output_dir / "id_trainval_results_long.csv", fieldnames, trainval_results)
    write_jsonl(output_dir / "id_trainval_tasks.jsonl", trainval_tasks)
    split_summaries["trainval"] = {
        "tasks": len(trainval_tasks),
        "rows": len(trainval_results),
        "source_splits": ["train", "val"],
    }

    return {
        "tasks": len(obs_matrix),
        "models": len(CANONICAL_MODELS),
        "rows": len(result_rows),
        "missing_cells": missing_cells,
        "splits": split_summaries,
        "source_matrix": "data/matrices/phase1_acrouter_v2/obs_matrix_clean.json",
    }


def export_ood_tables(output_dir: Path) -> dict[str, Any]:
    matrix = read_json(OOD_MATRIX)
    if matrix["models"] != CANONICAL_MODELS:
        raise ValueError(f"Unexpected OOD model order: {matrix['models']}")

    missing_cells = 0
    for task_id in matrix["ids"]:
        model_cells = matrix["matrix"][task_id]
        for model in CANONICAL_MODELS:
            if model not in model_cells:
                missing_cells += 1

    shutil.copy2(OOD_RESULTS_LONG, output_dir / "ood176_results_long.csv")
    shutil.copy2(OOD_TASKS, output_dir / "ood176_tasks.jsonl")

    return {
        "tasks": len(matrix["ids"]),
        "models": len(CANONICAL_MODELS),
        "rows": len(matrix["ids"]) * len(CANONICAL_MODELS) - missing_cells,
        "missing_cells": missing_cells,
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
      - split: train
        path: id_train_results_long.csv
      - split: validation
        path: id_val_results_long.csv
      - split: test
        path: id_test_results_long.csv
      - split: ood176
        path: ood176_results_long.csv
  - config_name: id_full
    data_files:
      - split: all
        path: id_results_long.csv
      - split: trainval
        path: id_trainval_results_long.csv
  - config_name: task_metadata
    data_files:
      - split: id_all
        path: id_tasks.jsonl
      - split: id_train
        path: id_train_tasks.jsonl
      - split: id_validation
        path: id_val_tasks.jsonl
      - split: id_test
        path: id_test_tasks.jsonl
      - split: id_trainval
        path: id_trainval_tasks.jsonl
      - split: ood176
        path: ood176_tasks.jsonl
---

# CodeRouterBench

CodeRouterBench is the benchmark data released with Agent-as-a-Router. The
core unit is a complete task-by-model result matrix: every benchmark task has
one recorded result for each of the eight canonical backend models.

## Associated Paper

- Hugging Face Daily Papers: [Agent-as-a-Router: Agentic Model Routing for Coding Tasks](https://huggingface.co/papers/2606.22902)
- arXiv: [2606.22902](https://arxiv.org/abs/2606.22902)

## Canonical Files

- `id_results_long.csv`: {summary["id"]["tasks"]:,} in-distribution tasks x 8 models = {summary["id"]["rows"]:,} result rows.
- `id_train_results_long.csv`: {summary["id"]["splits"]["train"]["tasks"]:,} train tasks x 8 models = {summary["id"]["splits"]["train"]["rows"]:,} result rows.
- `id_val_results_long.csv`: {summary["id"]["splits"]["val"]["tasks"]:,} validation tasks x 8 models = {summary["id"]["splits"]["val"]["rows"]:,} result rows.
- `id_test_results_long.csv`: {summary["id"]["splits"]["test"]["tasks"]:,} test tasks x 8 models = {summary["id"]["splits"]["test"]["rows"]:,} result rows.
- `id_trainval_results_long.csv`: train + validation combined for two-way train/test experiments.
- `ood176_results_long.csv`: 176 OOD tasks x 8 models = {summary["ood176"]["rows"]:,} result rows.
- `id_tasks.jsonl`: ID task metadata with split and dimension.
- `id_train_tasks.jsonl`, `id_val_tasks.jsonl`, `id_test_tasks.jsonl`, and `id_trainval_tasks.jsonl`: split-specific ID task metadata.
- `ood176_tasks.jsonl`: OOD176 task prompts and metadata.
- `models.json`: canonical model list and USD pricing metadata.
- `summary.json`: counts, source paths, and integrity checks.

Router outputs, baseline decisions, and paper tables are derived artifacts. The
benchmark itself is defined by the task tables above plus the per-model result
rows.

## Schemas

`id_results_long.csv` columns:

- `task_id`
- `split`: `train`, `val`, or `test`
- `dimension`
- `model`
- `score`: task score/performance used by the routing oracle
- `cost_usd`
- `total_tokens`
- `latency_ms`

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
