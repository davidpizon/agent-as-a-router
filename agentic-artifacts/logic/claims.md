# Claims

| id | claim | evidence | provenance |
| --- | --- | --- | --- |
| `claim:offline-repro` | The default bundle reproduces checked-in ID and current OOD176 results offline without live model calls. | `src/environment.md`, repository `README.md`, `tests/` | `derived-index` |
| `claim:router-loop` | ACRouter evaluates model selection through a Context-Action-Feedback loop with verifier-backed routing decisions. | `logic/solution/architecture.md`, `trace/exploration_tree.yaml` | `derived-index` |
| `claim:ood176` | On unified OOD176, ACRouter reaches 73.30 AvgPerf, 14.4 cumulative regret, 68.29 USD total cost, and 1.07 Perf/USD. | `evidence/tables/acrouter_release_summary.csv`, `outputs/acrouter_ood176/ood_metrics.json` | `checked-in-output` |
| `claim:baseline-coverage` | The release includes OOD176 comparisons for Oracle, ACRouter, online bandits, retrieval, trained-policy routers, single-model baselines, and random routing. | `evidence/tables/ood176_baseline_table.md`, `outputs/baselines_ood176/` | `checked-in-output` |
| `claim:cost-aware` | Evaluation tracks quality, cost, cumulative regret, and Perf/USD instead of reporting only raw pass rate. | `src/configs/router_eval.md`, `evidence/tables/score_matrix.md` | `derived-index` |
| `claim:extensible-pipeline` | Users can add custom models or benchmark tasks through a config-driven one-command pipeline. | `configs/eval_pipeline.example.json`, `scripts/run_pipeline.py`, `examples/custom_benchmark/` | `derived-index` |
| `claim:workflow-api` | ACRouter can be imported during inference and connected to arbitrary model-caller and verifier functions. | `src/acrouter_repro/inference.py`, `examples/inference_demo.py` | `derived-index` |

## Notes

The claims are intentionally compact so agents can load only the evidence files
needed for a specific question. Failed or rejected design paths are recorded in
`trace/exploration_tree.yaml`.
