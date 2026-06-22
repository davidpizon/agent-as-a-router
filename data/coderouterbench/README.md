---
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

## Canonical Files

- `id_results_long.csv`: 9,999 in-distribution tasks x 8 models = 79,992 result rows.
- `id_train_results_long.csv`: 6,067 train tasks x 8 models = 48,536 result rows.
- `id_val_results_long.csv`: 1,013 validation tasks x 8 models = 8,104 result rows.
- `id_test_results_long.csv`: 2,919 test tasks x 8 models = 23,352 result rows.
- `id_trainval_results_long.csv`: train + validation combined for two-way train/test experiments.
- `ood176_results_long.csv`: 176 OOD tasks x 8 models = 1,408 result rows.
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

- `data/matrices/phase1_acrouter_v2/obs_matrix_clean.json`
- `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json`
