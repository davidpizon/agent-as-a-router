# OOD176 Baseline Table

Generated: 2026-06-13 15:13:48 UTC

Left-side in-distribution metrics are copied unchanged from the provided table. Right-side OOD metrics are recomputed on the unified OOD176 matrix.

| Group | Router | ID AvgPerf% | ID CumReg | ID Perf/$ | OOD n | OOD AvgPerf% | OOD CumReg | OOD Perf/$ | Source |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Bound | Oracle | 57.00 | 0.0 | 8.20 | 176 | 78.98 | 0.0 | 3.28 | reward_oracle |
| Agent-as-a-Router | ACRouter (ours) | 49.98 | 205.5 | 3.79 | 176 | 73.30 | 14.4 | 1.07 | acrouter_unique_release_ood176 |
| Dynamic: Online Bandit | LinTS | 46.48 | 307.4 | 4.49 | 176 | 57.95 | 40.5 | 0.99 | online_lints_cost_aware |
| Dynamic: Online Bandit | LinUCB | 46.84 | 296.9 | 4.38 | 176 | 57.95 | 40.0 | 1.07 | online_linucb_cost_aware |
| Static: Heuristic | DimensionBest | 47.50 | 277.4 | 3.69 | --- | --- | --- | --- | not_applicable_to_ood |
| Static: Heuristic | kNN Retrieval | 47.18 | 286.7 | 6.07 | 176 | 35.23 | 75.1 | 6.37 | online_knn_retrieval |
| Static: Trained Policy | LogReg | 47.26 | 284.4 | 6.27 | 176 | 28.98 | 86.3 | 3.88 | old112_published_replay_plus_new64_router_or_modal:T1_LogReg_metrics.json |
| Static: Trained Policy | RouteLLM-BERT | 47.22 | 285.5 | 6.22 | 176 | 31.82 | 81.2 | 5.25 | old112_published_replay_plus_new64_router_or_modal:T4_RouteLLM_SW_metrics.json |
| Static: Trained Policy | TF-IDF+MLP | 46.97 | 292.8 | 6.11 | 176 | 13.07 | 114.1 | 2.60 | old112_published_replay_plus_new64_router_or_modal:T2_TFIDF_MLP_metrics.json |
| Static: Trained Policy | Qwen3.5-0.8B-Finetuned | 46.41 | 309.1 | 6.82 | 176 | 23.86 | 95.8 | 1.96 | old112_published_replay_plus_new64_router_or_modal:L2_ft08b_router_v3_metrics.json |
| Static: Trained Policy | RouteLLM-MF | 46.16 | 316.5 | 6.19 | 176 | 32.95 | 79.0 | 7.93 | old112_published_replay_plus_new64_router_or_modal:T3_RouteLLM_MF_metrics.json |
| Single-Model Baselines | Always-Opus 4.6 | 43.83 | 387.1 | 1.29 | 176 | 63.64 | 44.1 | 0.33 | always:claude-opus-4-6 |
| Single-Model Baselines | Always-Kimi-K2.5 | 36.66 | 593.3 | 12.62 | 176 | 19.89 | 101.7 | 13.60 | always:kimi-k2.5 |
| Single-Model Baselines | Always-Qwen3.5-Plus | 37.16 | 580.2 | 2.05 | 176 | 27.27 | 89.2 | 4.39 | always:qwen3.5-plus |
| Single-Model Baselines | Random | 38.75 | 533.6 | 2.48 | 176 | 40.34 | 71.0 | 0.75 | random_10_seed_mean |

## Notes

- Oracle: Cost-aware reward oracle with epsilon=(1,-0.1).
- ACRouter (ours): ACRouter release OOD176 decisions from run_acrouter_ood176.py. Source metrics file reports AvgPerf=73.3 CumReg=14.4 $Total=68.29.
- LinTS: Offline online replay over the OOD176 task order.
- LinUCB: Offline online replay over the OOD176 task order.
- DimensionBest: DimensionBest remains not applicable to OOD because unseen agentic tasks lack a predefined dimension-to-model map.
- kNN Retrieval: Online kNN replay using task metadata/hash features and observed chosen-model rewards.
- LogReg: Old112 published decisions replayed; New64 is predicted by the saved LogReg router on real New64 prompts.
- RouteLLM-BERT: No published RouteLLM-BERT legacy OOD112 decision file was found in this worktree; uses the available T4_RouteLLM_SW legacy OOD112 decisions as the closest published RouteLLM proxy for the Old112 portion, and predicts New64 with the saved RouteLLM-SW router on real prompts.
- TF-IDF+MLP: Old112 published decisions replayed; New64 is predicted by the saved TF-IDF+MLP router on real New64 prompts.
- Qwen3.5-0.8B-Finetuned: Old112 uses the available L2_ft08b_router_v3 decisions; this file's published legacy OOD112 resolved_pct is 25.00, not the 55.36 value in the provided LaTeX table. New64 uses modal extension.
- RouteLLM-MF: Old112 published decisions replayed; New64 is predicted by the saved RouteLLM-MF router on real New64 prompts.
- Random: Mean over seeds 42-51; per-seed decisions are in decisions/.
