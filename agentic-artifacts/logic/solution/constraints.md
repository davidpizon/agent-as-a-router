# Constraints

- This artifact folder is a navigable release surface, not a replacement for
  the canonical data under `data/` or reference outputs under `outputs/`.
- Numeric claims in this folder are limited to checked-in repository outputs.
- Default reproduction uses cached/offline data and does not require live model
  service calls.
- Live Docker or Apptainer verification is optional and requires host-level
  sandbox tooling plus external SWE-bench assets.
- Cost-aware comparisons should use the same score, pricing, task stream, and
  reward assumptions recorded in `src/configs/router_eval.md`.
- `DimensionBest` is not reported for OOD176 because unseen agentic tasks do
  not have the predefined dimension-to-model map required by that heuristic.

