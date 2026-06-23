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

- `id_results_long.csv`: 9,999 in-distribution tasks x 8 models = 79,992 result rows.
- `id_probing_results_long.csv`: 7,080 probing tasks x 8 models = 56,640 result rows. This is the merged original train + validation set.
- `id_test_results_long.csv`: 2,919 ID test tasks x 8 models = 23,352 result rows.
- `ood176_results_long.csv`: 176 OOD tasks x 8 models = 1,408 result rows.
- `id_tasks.jsonl`: ID task metadata with split and dimension.
- `id_probing_tasks.jsonl` and `id_test_tasks.jsonl`: split-specific ID task metadata.
- `ood176_tasks.jsonl`: OOD176 task prompts and metadata.
- `models.json`: canonical model list and USD pricing metadata.
- `summary.json`: counts, source paths, and integrity checks.

Router outputs, baseline decisions, and paper tables are derived artifacts. The
benchmark itself is defined by the task tables above plus the per-model result
rows.

## Download Or Load

Download the full public benchmark snapshot:

```bash
hf download Lance1573/CodeRouterBench --repo-type dataset --local-dir .hf/CodeRouterBench
```

Load the default benchmark tables with `datasets`:

```python
from datasets import load_dataset

bench = load_dataset("Lance1573/CodeRouterBench")
print(bench)
```

The GitHub reproduction scripts can use the downloaded snapshot directly via:

```bash
python scripts/run_acrouter_ood176.py --hf-dataset-dir .hf/CodeRouterBench
```

For ID rows, `cost_usd` is computed from `data/id/tokens.jsonl` and
`data/matrices/phase1_id/model_pricing.json`. Rows without a token record leave
`cost_usd`, `input_tokens`, and `output_tokens` blank unless the compact log
records zero total tokens; zero-token rows use
`cost_source=missing_token_record_zero_total`. The current export has
148 such legacy rows and
408.082583 USD of computed ID cost.

For OOD176 rows, `cost_usd` is recomputed from `in_tok`, `out_tok`, and the same
pricing table. The current export has 422.147494
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

- `data/matrices/phase1_acrouter_v2/obs_matrix_clean.json`
- `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json`
