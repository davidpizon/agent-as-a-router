# Router Evaluation Configuration

## Streams

- CodeRouterBench ID: 9,999 in-distribution coding tasks x 8 backend models.
- ID reproduction split: 2,919 in-distribution test tasks.
- OOD176: current public OOD matrix unified from Old112 plus filtered New64,
  176 tasks x 8 backend models.

## Metrics

- `AvgPerf%`: average task performance percentage.
- `CumReg`: cumulative cost-aware regret relative to the configured oracle.
- `$Total`: total logged backend cost in USD.
- `Perf/$`: average performance divided by total cost.
- `Apply_ok%`: patch apply success percentage when available.
- `rAcc`: reward-oracle agreement or related reward-accuracy metric.

## Main Cost Entries

| split | n | router | total cost USD | source |
| --- | ---: | --- | ---: | --- |
| ID | 2919 | ACRouter | 22.91 | `outputs/current/summary.json` |
| OOD176 | 176 | ACRouter | 68.29 | `outputs/acrouter_ood176/ood_metrics.json` |

## Legacy OOD112 Supplement

| split | n | router | total cost USD | source |
| --- | ---: | --- | ---: | --- |
| Legacy OOD112 | 112 | ACRouter | 51.70 | `outputs/current/summary.json` |

## OOD176 Baseline Sources

- Paper-style table: `evidence/tables/ood176_baseline_table.md`
- Metrics CSV mirror: `evidence/tables/ood176_baseline_metrics.csv`
- Canonical full outputs: `outputs/baselines_ood176/`
- Decision JSONL files: `outputs/baselines_ood176/decisions/`

## Custom Evaluation Pipeline

- Config example: `configs/eval_pipeline.example.json`
- CLI: `scripts/run_pipeline.py`
- Task/result example: `examples/custom_benchmark/`
- Inference API demo: `examples/inference_demo.py`

## Bindings

- `logic/claims.md`
- `logic/experiments.md`
- `evidence/tables/acrouter_release_summary.csv`
- `evidence/tables/score_matrix.md`
