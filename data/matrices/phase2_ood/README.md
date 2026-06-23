# OOD Dataset

Unified OOD176 bundle for router testing.

## Layout

- `raw/old112/matrix.json`: original Old112 ACRouter OOD matrix.
- `raw/new64/matrix.{json,csv,md}`: original New64 comparable matrix snapshot.
- `unified/matrix_acrouter_ood176.json`: ACRouter release-compatible 176-task matrix.
- `unified/acrouter_v2_obs_matrix.json`: `acrouter_v2` observation matrix.
- `unified/tasks.jsonl`: task metadata for all 176 rows.
- `unified/results_long.csv`: normalized long-form per-task/per-model table.
- `acrouter_v2_data/processed/*.jsonl`: processed task files loadable by `acrouter_v2.data_utils.load_tasks`.
- `scripts/run_acrouter_ood176.py`: one-command ACRouter OOD176 entrypoint.
- `scripts/run_baselines_ood176.py`: one-command replay for the main-table OOD baselines on the 176-task matrix.

## Model Mapping

Old112 already uses the ACRouter release model names. New64 raw model names are mapped as follows:

| New64 model | ACRouter canonical model |
| --- | --- |
| `claude-opus-4-6` | `claude-opus-4-6` |
| `claude-sonnet-4-6` | `claude-sonnet-4-6` |
| `gpt-5.4-medium` | `gpt-5.4` |
| `glm-5` | `glm-5` |
| `kimi-k2.6` | `kimi-k2.5` |
| `MiniMax-M2.5` | `MiniMax-M2.7` |
| `qwen3.5-plus` | `qwen3.5-plus` |
| `qwen3.6-plus` | `Qwen3-Max` |

New64 status cells preserve the original model name in `source_model`; token and cost fields use
Old112 per-model means as fallback values because the New64 matrix snapshot is pass/fail only.

## Summary

- Generated: 2026-06-23 16:36:06 UTC
- Old112 tasks: 112
- Old112 tasks with real prompts: 112
- Old112 prompt source: `data/matrices/phase2_ood/unified/tasks.jsonl`
- New64 tasks: 64
- New64 tasks with real prompts: 64
- New64 prompt source: `data/matrices/phase2_ood/unified/tasks.jsonl`
- Combined tasks: 176
- Models: `claude-opus-4-6`, `claude-sonnet-4-6`, `gpt-5.4`, `glm-5`, `kimi-k2.5`, `MiniMax-M2.7`, `Qwen3-Max`, `qwen3.5-plus`

Run:

```bash
python scripts/run_acrouter_ood176.py
python scripts/run_baselines_ood176.py
```

Baseline outputs are written to `outputs/baselines_ood176/`:

- `baseline_table.{md,csv,tex}`: main table with in-distribution columns kept unchanged and OOD columns recomputed at `n=176`.
- `baseline_metrics.{json,csv}`: full metric payloads and decision-source notes.
- `decisions/*.jsonl`: per-task decisions for each applicable baseline.

For trained-policy baselines where only published OOD112 decisions are available in this worktree,
the Old112 portion is replayed from those decisions. When a saved router is available, the New64
portion is predicted from the task prompt; otherwise it uses a documented modal extension from the
Old112 decisions. The output notes record the exact source file and extension/prediction path.
