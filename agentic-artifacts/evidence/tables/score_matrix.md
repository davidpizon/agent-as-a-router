# Score Matrix Pointers

The artifact folder keeps compact pointers to the full checked-in matrices
rather than duplicating every matrix row.

## Canonical Matrix Files

| purpose | path | notes |
| --- | --- | --- |
| CodeRouterBench dataset card | `data/coderouterbench/README.md` | Human/HF-facing benchmark definition and schema. |
| CodeRouterBench ID results | `data/coderouterbench/id_results_long.csv` | 9,999 ID tasks x 8 models = 79,992 result rows. |
| CodeRouterBench ID probing results | `data/coderouterbench/id_probing_results_long.csv` | Original train + validation merged: 7,080 tasks x 8 models = 56,640 result rows. |
| CodeRouterBench ID test results | `data/coderouterbench/id_test_results_long.csv` | Held-out ID test: 2,919 tasks x 8 models = 23,352 result rows. |
| CodeRouterBench OOD176 results | `data/coderouterbench/ood176_results_long.csv` | 176 OOD tasks x 8 models = 1,408 result rows. |
| CodeRouterBench model metadata | `data/coderouterbench/models.json` | Eight canonical backend models and pricing metadata. |
| New64 raw matrix | `data/matrices/phase2_ood/raw/new64/matrix.json` | Filtered New64 subset and excluded SWE-CI IDs. |
| Old112 raw matrix | `data/matrices/phase2_ood/raw/old112/matrix.json` | Raw Old112 snapshot. |
| OOD176 unified matrix | `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json` | Main unified OOD176 scoring matrix. |
| OOD176 long results | `data/matrices/phase2_ood/unified/results_long.csv` | Long-form per-task/per-model results. |
| OOD176 task list | `data/matrices/phase2_ood/unified/tasks.jsonl` | Task metadata for unified OOD176. |
| Phase-1 observation matrix | `data/matrices/phase1_acrouter_v2/obs_matrix_clean.json` | Source for public ID task x model results. |
| Phase-1 response matrix | `data/matrices/phase1_acrouter_v2/response_matrix.json` | Compact phase-1 response matrix. |
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
