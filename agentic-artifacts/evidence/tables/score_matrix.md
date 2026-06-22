# Score Matrix Pointers

The artifact folder keeps compact pointers to the full checked-in matrices
rather than duplicating every matrix row.

## Canonical Matrix Files

| purpose | path | notes |
| --- | --- | --- |
| New64 raw matrix | `data/matrices/phase2_ood/raw/new64/matrix.json` | Filtered New64 subset and excluded SWE-CI IDs. |
| Old112 raw matrix | `data/matrices/phase2_ood/raw/old112/matrix.json` | Raw Old112 snapshot. |
| OOD176 unified matrix | `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json` | Main unified OOD176 scoring matrix. |
| OOD176 long results | `data/matrices/phase2_ood/unified/results_long.csv` | Long-form per-task/per-model results. |
| OOD176 task list | `data/matrices/phase2_ood/unified/tasks.jsonl` | Task metadata for unified OOD176. |
| Phase-1 response matrix | `data/matrices/phase1_acrouter_v2/response_matrix.json` | Compact phase-1 observation matrix. |
| Legacy OOD112 matrix | `data/ood/matrix.json` | Legacy OOD matrix used by cached sandbox replay. |

## Expected Row Schema

Matrix rows or normalized long-form entries should expose:

- task id
- stream or split
- model id
- score or pass signal
- backend cost
- verifier/apply status when available
- regret-ready reward field
- provenance or source tag

## Custom Matrix Input

For new benchmarks, either provide this matrix schema directly to
`scripts/run_pipeline.py` or provide:

- `tasks.jsonl`: one row per task with `task_id` or `id`.
- `model_results.jsonl`: one row per task/model with `task_id`, `model`, and
  either `resolved` or `score`.

The example lives in `examples/custom_benchmark/`.

## Evidence Bindings

- ACRouter summary: `evidence/tables/acrouter_release_summary.csv`
- Legacy OOD112 summary: `evidence/tables/legacy_ood112_summary.csv`
- OOD176 baseline metrics: `evidence/tables/ood176_baseline_metrics.csv`
- Full baseline outputs: `outputs/baselines_ood176/`
