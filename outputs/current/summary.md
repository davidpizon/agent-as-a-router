# ACRouter Unique Release Results

| split | n | AvgPerf% | CumReg | $Total | Perf/$ | rAcc | extras |
|---|---:|---:|---:|---:|---:|---:|---|
| ID | 2919 | 50.14 | 202.0 | 22.31 | 2.25 | 0.2395 | missing_score=1, policy=hierarchical, tune=train+val, eval=test, leakage=none |
| OOD | 112 | 66.96 | 13.7 | 63.43 | 1.06 | 0.5804 | apply_ok=77.68%, escalations=18, avg_steps=3.10 |

ID uses the configured clean policy shown in the table. OOD uses the k=2 verify-and-escalate cascade with an explicit sandbox verifier: MiniMax -> Kimi -> GPT-5.4 -> GLM-5, then Opus only when at least two cheap attempts produce apply_ok.
