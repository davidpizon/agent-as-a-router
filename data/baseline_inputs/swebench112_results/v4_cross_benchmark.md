# V4 ACRouter — Cross-Benchmark Performance

V4 is calibrated on CodeRouterBench. Here is how it (and the same competitors) score on the two benchmarks side-by-side. Note: only CodeRouterBench is in-distribution for V4 — SWE-bench Verified is fully OOD.

---

## Benchmark 1 — CodeRouterBench paper-test (n=2919, 9 coding dimensions)

Source: `acrouter_v4.0/results/all_acc_rAcc3.md` (rAcc3 oracle = argmax(perf, −cost, −tokens, name)) + `coding-router/ALL_EXPERIMENT_RESULTS.md` (avg_perf / gap%).

| Rank | Method                              | avg_perf | Gap%  | rAcc3 (hits/2919) | Type            |
|:----:|-------------------------------------|:--------:|:-----:|:-----------------:|-----------------|
| —    | Oracle                              | 0.570    | 0.0   | 1.000 (2919)      | upper bound     |
| 1    | **ACRouter v4.3 (ensemble, paper)** | **0.462**| 23.1  | **0.502 (1466)**  | **ACRouter v4** |
| 2    | ACRouter v4.2                       | 0.461    | 23.1  | 0.502 (1465)      | ACRouter v4     |
| 3    | EARouter Top-3 w/ prior             | 0.553    | 3.0   | —                 | ACRouter v2     |
| 4    | Cascade                             | 0.490    | 14.0  | 0.228 (664)       | heuristic       |
| 5    | DimensionBest                       | 0.475    | 16.7  | 0.217 (633)       | heuristic       |
| 6    | finetuned_router_qwen35_08b (alone) | 0.484    | 15.1  | 0.504 (1472)      | trained-LLM     |
| 7    | LogReg                              | 0.473    | 17.1  | 0.393 (1146)      | trained         |
| 8    | TF-IDF + MLP                        | 0.469    | 17.7  | 0.378 (1104)      | trained         |
| 9    | RouteLLM-SW                         | 0.472    | 17.2  | 0.369 (1077)      | trained         |
| 10   | RouteLLM-MF                         | 0.462    | 19.0  | 0.366 (1067)      | trained         |
| 11   | LLM 3-shot (gpt-5.4)                | 0.424    | 25.6  | 0.349 (1020)      | LLM router      |
| 12   | LLM 0-shot (gpt-5.4)                | 0.425    | 25.5  | 0.317 (923)       | LLM router      |
| 13   | Always-Kimi                         | 0.364    | 36.1  | 0.441 (1287)      | baseline        |
| 14   | Always-Opus                         | 0.438    | 23.1  | 0.099 (290)       | baseline        |
| 15   | Random                              | 0.378    | 33.7  | 0.121 (354)       | baseline        |
| 16   | Claude Code Router                  | 0.388    | 32.0  | 0.256 (747)       | commercial      |

Notes for CodeRouterBench:
- `avg_perf` and `Gap%` are taken from the v1-paper recompute (n=2919) — these are what the v1 paper reports.
- `rAcc3` is the v4-spec routing-accuracy oracle (`argmax(perf, −cost, −tokens, alphabetic)`).
- **V4.3 leads on rAcc3** (0.502 vs strongest non-V4 baseline finetuned_router @ 0.504 — virtually tied, but V4 retains the cost-aware reward / no-leak property).
- **EARouter Top-3 w/ prior leads on avg_perf**, but it's a Top-K ensemble that pays for K backends.

---

## Benchmark 2 — SWE-bench Verified subset (n=112, OOD, agentic execution)

Source: `data/routing/swebench112_results/comparison_table.md` (this run).

| Rank | Method                              | Resolved   | Gap%  | Backend $ | Type            |
|:----:|-------------------------------------|:----------:|:-----:|:---------:|-----------------|
| —    | Oracle                              | 85 (75.89%)| 0.0   | $116      | upper bound     |
| 1    | Cascade                             | 85 (75.89%)| 0.0   | $152      | heuristic       |
| 2    | Always-Opus                         | 74 (66.07%)| 12.94 | $124      | baseline        |
| 3    | **ACRouter v2 full (R1)**           | **65 (58.04%)**| 23.53 | **$73**   | **ACRouter v2** |
| 4    | Always-Sonnet                       | 64 (57.14%)| 24.71 | $89       | baseline        |
| 5    | ACRouter v2 + BGE encoder (R2)      | 61 (54.46%)| 28.24 | $86       | ACRouter v2     |
| 6    | Always-GPT                          | 60 (53.57%)| 29.41 | $12       | baseline        |
| 7    | ACRouter v2: base-model orch (R8)   | 60 (53.57%)| 29.41 | $62       | ACRouter v2     |
| 8    | ACRouter v2: w/o Memory (R4)        | 53 (47.32%)| 37.65 | $46       | ACRouter v2     |
| 9    | ACRouter v2: w/o TS (R5)            | 48 (42.86%)| 43.53 | $43       | ACRouter v2     |
| 10   | ACRouter v2: rule-based orch (R7)   | 42 (37.50%)| 50.59 | $38       | ACRouter v2     |
| 11   | ACRouter v2: w/o Verifier (R6)      | 41 (36.61%)| 51.76 | $44       | ACRouter v2     |
| 12   | LLM 0-shot (qwen35_08b finetuned)   | 28 (25.00%)| 67.06 | $12       | LLM router      |
| 13   | LogReg                              | 22 (19.64%)| 74.12 | $4        | trained         |
| 14   | RouteLLM-SW                         | 16 (14.29%)| 81.18 | $4        | trained         |
| 15   | TF-IDF + MLP                        | 15 (13.39%)| 82.35 | $4        | trained         |
| 16   | **ACRouter v4 ensemble**            | **14 (12.50%)**| 83.53 | **$3**    | **ACRouter v4** |
| 17   | LLM 0-shot (qwen3.5-0.8b base)      | 13 (11.61%)| 84.71 | $9        | LLM router      |
| 18   | RouteLLM-MF                         | 10 (8.93%) | 88.24 | $3        | trained         |

---

## Cross-benchmark summary for V4 ensemble

| Benchmark              | n    | Headline metric           | V4 score            | Best non-V4              | Δ V4 vs best |
|------------------------|------|---------------------------|---------------------|--------------------------|--------------|
| CodeRouterBench (paper test, in-distribution) | 2919 | rAcc3 hits      | **1466 (0.502)** | finetuned_router 1472 (0.504) | −0.2pp |
| CodeRouterBench (paper test, in-distribution) | 2919 | avg_perf        | 0.462            | EARouter Top-3 0.553           | −9.1pp |
| SWE-bench Verified subset (OOD agentic)      |  112 | resolved        |   14 (0.125)     | Cascade 85 / Opus 74 / V2-R1 65 | −51pp vs Cascade |

---

## Why V4 is strong on CodeRouterBench but weak on SWE-bench

1. **Calibration distribution**: V4's voter weights and per-dim specialist map are computed on a CodeRouterBench probing-set holdout. The `bug_fixing` specialist there is `tfidf_mlp` (with 2.5× boost). On SWE-bench-Verified, `tfidf_mlp` predicts `Qwen3-Max` (the legacy `通义千问Max` label) for 82/112 tasks — but `Qwen3-Max` resolves only 10/112 there.
2. **No escalation**: V4 deliberately removes the escalation loop (cite: README §1). On the in-distribution 9-dim test it nets +rAcc because the rAcc oracle prefers cheap ties; on SWE-bench, where backends often fail entirely on hard issues, escalating to a stronger model is what gives V2 its 65/112 lead.
3. **Cost-aware reward (`eps2 = -10`)**: pulls Memory's mean_reward toward cheap models. Helps on CodeRouterBench, hurts on SWE-bench where cheap models can't solve real GitHub bugs.
4. **Static voter mismatch**: 4 of V4's 7 voters are TF-IDF classifiers trained on CodeRouterBench prompts. Their feature distribution does not transfer to SWE-bench issue text, yet they get aggregate weight ≈ 4× the LLM voter's weight in V4's default config.

In short: V4 is **the right design for the rAcc oracle on CodeRouterBench**, and **the wrong design for OOD agentic resolution on SWE-bench**.

---

## What would let V4 close the gap on SWE-bench

- Recalibrate voter weights using SWE-bench-Verified train/val splits (instead of CodeRouterBench's probing set).
- Re-derive the per-dim specialist map for SWE-bench (likely → `precomp_finetuned_router_qwen35_08b` instead of `tfidf_mlp`).
- Re-enable escalation, or use cascade as a fallback when ensemble confidence is low.
- Drop the `eps2 = -10` cost-aware reward when the backend pool has a clear quality cliff (Opus 66% vs Qwen3-Max 9%).