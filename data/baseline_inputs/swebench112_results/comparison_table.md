# SWE-bench Verified 112 — Routing Methods Comparison

> Subset: 112 tasks (Opus-resolved ∩ filtered keep=true)
> Backbone: mini-swe-agent + apptainer sandbox
> Oracle (any-of-8 resolves): **85/112 = 75.89%**

| Rank | Method | Type | Resolved | Gap% | apply_ok | non_empty | Backend $ | Router $ | Perf/$ | Router tok(in/out) |
|:---:|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| — | **Oracle** | upper bound | 85/112 (75.89%) | 0.00% | 104 | 105 | $116.49 | $0.00 | 0.73 | — |
| 1 | Cascade | heuristic | 85/112 (75.89%) | 0.00% | 112 | 112 | $151.70 | $0.00 | 0.56 | 0/0 |
| 2 | Always-Opus | baseline | 74/112 (66.07%) | 12.94% | 95 | 96 | $124.03 | $0.00 | 0.60 | 0/0 |
| 3 | **ACRouter v2 full** | ACRouter v2 (ours) | 65/112 (58.04%) | 23.53% | 76 | 77 | $72.83 | $0.00 | 0.89 | 91,662/1,541 |
| 4 | Always-Sonnet | baseline | 64/112 (57.14%) | 24.71% | 89 | 90 | $89.36 | $0.00 | 0.72 | 0/0 |
| 5 | ACRouter v2: BGE encoder | ACRouter abl. | 61/112 (54.46%) | 28.24% | 73 | 74 | $85.97 | $0.00 | 0.71 | 91,676/1,543 |
| 6 | Always-GPT | baseline | 60/112 (53.57%) | 29.41% | 110 | 110 | $11.62 | $0.00 | 5.16 | 0/0 |
| 7 | ACRouter: base-model orch. | ACRouter abl. | 60/112 (53.57%) | 29.41% | 71 | 72 | $61.88 | $0.00 | 0.97 | 91,726/10,071 |
| 8 | ACRouter: w/o Memory | ACRouter abl. | 53/112 (47.32%) | 37.65% | 65 | 66 | $46.06 | $0.00 | 1.15 | 71,833/1,526 |
| 9 | ACRouter: w/o TS scheduler | ACRouter abl. | 48/112 (42.86%) | 43.53% | 59 | 60 | $42.74 | $0.00 | 1.12 | 96,179/1,600 |
| 10 | ACRouter: rule-based orch. | ACRouter abl. | 42/112 (37.50%) | 50.59% | 57 | 58 | $38.21 | $0.00 | 1.10 | 0/0 |
| 11 | ACRouter: w/o Verifier | ACRouter abl. | 41/112 (36.61%) | 51.76% | 55 | 56 | $43.52 | $0.00 | 0.94 | 91,655/1,535 |
| 12 | Random | baseline | 34/112 (30.36%) | 60.00% | 52 | 53 | $33.09 | $0.00 | 1.03 | 0/0 |
| 13 | Always-GLM5 | baseline | 32/112 (28.57%) | 62.35% | 46 | 47 | $24.34 | $0.00 | 1.31 | 0/0 |
| 14 | LLM 0-shot (qwen35_08b_router_v3, finetuned) | LLM router | 28/112 (25.00%) | 67.06% | 39 | 40 | $11.65 | $0.00 | 2.40 | 75,233/1,602 |
| 15 | LogReg (TF-IDF) | trained | 22/112 (19.64%) | 74.12% | 33 | 33 | $3.60 | $0.00 | 6.11 | 0/0 |
| 16 | Always-Kimi | baseline | 21/112 (18.75%) | 75.29% | 30 | 31 | $0.93 | $0.00 | 22.58 | 0/0 |
| 17 | Always-MiniMax | baseline | 16/112 (14.29%) | 81.18% | 20 | 20 | $0.00 | $0.00 | ∞ | 0/0 |
| 18 | RouteLLM-SW | trained | 16/112 (14.29%) | 81.18% | 27 | 28 | $3.52 | $0.00 | 4.55 | 0/0 |
| 19 | TF-IDF + MLP | trained | 15/112 (13.39%) | 82.35% | 24 | 24 | $4.28 | $0.00 | 3.50 | 0/0 |
| 20 | ACRouter v4 (ensemble, cost-aware, no-escalation) | ACRouter v4 (ours) | 14/112 (12.50%) | 83.53% | 21 | 21 | $2.64 | $0.00 | 5.30 | 64,369/1,614 |
| 21 | LLM 0-shot (qwen3.5-0.8b) | LLM router | 13/112 (11.61%) | 84.71% | 18 | 18 | $9.42 | $0.00 | 1.38 | 75,233/10,752 |
| 22 | RouteLLM-MF | trained | 10/112 (8.93%) | 88.24% | 21 | 22 | $2.64 | $0.00 | 3.79 | 0/0 |
| 23 | Always-QwenMax | baseline | 10/112 (8.93%) | 88.24% | 22 | 23 | $2.68 | $0.00 | 3.73 | 0/0 |
| 24 | Always-Qwen3.5+ | baseline | 3/112 (2.68%) | 96.47% | 6 | 6 | $3.95 | $0.00 | 0.76 | 0/0 |

## Legend
- **Resolved**: tasks where at least one applied patch passes all `FAIL_TO_PASS` tests (and `PASS_TO_PASS` still pass).
- **Gap%**: `(Oracle − resolved) / Oracle × 100`. Lower = closer to oracle.
- **apply_ok**: tasks whose patch applies cleanly (resolved ⊆ apply_ok ⊆ non_empty).
- **Backend $**: total $ spent on backend model generation (opus / sonnet / gpt / etc.).
- **Router $**: $ spent on the router LLM itself (≈ 0 for local Qwen).
- **Perf/$**: resolved / (backend$ + router$) — higher = more efficient.
- **Router tok(in/out)**: router-LLM token usage (for LLM/Agent routers only).

## Module-level ablations (ACRouter v2)

| Module dropped | Resolved | Δ vs full | Cost |
|---|:---:|:---:|:---:|
| hash → BGE encoder | 61/112 (54.46%) | -4 pp | $85.97 |
| w/o Memory | 53/112 (47.32%) | -12 pp | $46.06 |
| w/o TS scheduler | 48/112 (42.86%) | -17 pp | $42.74 |
| w/o Verifier | 41/112 (36.61%) | -24 pp | $43.52 |
| LLM policy → rule-based | 42/112 (37.50%) | -23 pp | $38.21 |
| finetuned → base-model policy | 60/112 (53.57%) | -5 pp | $61.88 |
