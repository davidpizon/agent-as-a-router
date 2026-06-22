# ACRouter Unique Release Results

| split | n | AvgPerf% | CumReg | $Total | Perf/$ | rAcc | extras |
|---|---:|---:|---:|---:|---:|---:|---|
| ID | 2919 | 50.14 | 201.9 | 22.91 | 2.19 | 0.2395 | missing_score=1, policy=hierarchical, tune=train+val, eval=test, leakage=none |
| OOD | 112 | 66.96 | 12.8 | 51.70 | 1.30 | 0.6786 | apply_ok=77.68%, escalations=18, avg_steps=3.10 |

ID uses the configured clean policy shown in the table. OOD uses the k=2 verify-and-escalate cascade with an explicit sandbox verifier: MiniMax -> Kimi -> GPT-5.4 -> GLM-5, then Opus only when at least two cheap attempts produce apply_ok.
