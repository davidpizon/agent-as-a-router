# ACRouter Agentic Artifact Entry

Protocol: Agent-Native Research Artifact
Status: open-source-ready
Updated: 2026-06-22
Repository: ACRouter open-source bundle

This root manifest lets an agent decide whether the ACRouter artifact is
relevant before loading deeper files. It indexes the logic, source
configuration, exploration trace, and evidence layers for offline reproduction
of ACRouter and OOD176 baselines.

## Layers

- `README.md`: load order and scope for automated readers.
- `manifest.json`: machine-readable index of paths, commands, and key metrics.
- `logic/claims.md`: falsifiable claims and evidence bindings.
- `logic/experiments.md`: benchmark streams, splits, and headline results.
- `logic/solution/architecture.md`: ACRouter components and feedback loop.
- `logic/solution/constraints.md`: scope and interpretation constraints.
- `src/environment.md`: runtime and reproducibility assumptions.
- `src/configs/router_eval.md`: scoring, cost, and evaluation configuration.
- `trace/exploration_tree.yaml`: decision graph with rejected paths preserved.
- `evidence/tables/acrouter_release_summary.csv`: compact ID/OOD summary.
- `evidence/tables/ood176_baseline_metrics.csv`: OOD176 baseline metrics.
- `evidence/tables/ood176_baseline_table.md`: paper-style baseline table.
- `evidence/tables/score_matrix.md`: full score-matrix pointers and schema.
- `evidence/figures/README.md`: figure/data-product pointers.
- `../data/coderouterbench/`: canonical CodeRouterBench task x model tables.

## Key Claims

- `claim:offline-repro`: The default artifact reproduces checked-in ID and
  current OOD176 results offline without live model calls.
- `claim:router-loop`: ACRouter evaluates routing as a
  Context-Action-Feedback loop with verifier-backed decisions.
- `claim:ood176`: On the unified OOD176 matrix, ACRouter reaches 73.30
  AvgPerf, 14.4 cumulative regret, 68.29 USD total cost, and 1.07 Perf/USD.
- `claim:baseline-coverage`: The bundle includes Oracle, ACRouter, online
  bandits, retrieval, trained-policy, single-model, and random OOD176 baselines.
- `claim:cost-aware`: Router evaluation tracks quality, cost, regret, and
  Perf/USD rather than only raw pass rate.
- `claim:coderouterbench`: CodeRouterBench is released as complete ID and
  OOD176 task x 8-model result tables, with router outputs treated as derived
  artifacts.
- `claim:extensible-pipeline`: Users can add custom models or benchmark tasks
  through `scripts/run_pipeline.py` without editing built-in OOD176 files.
- `claim:workflow-api`: `acrouter_repro.inference.ACRouter` can be imported as
  a routing module inside arbitrary inference workflows.

## Cross-Layer Bindings

- `claim:offline-repro` -> `src/environment.md` -> repository `README.md` ->
  `tests/`
- `claim:router-loop` -> `logic/solution/architecture.md` ->
  `src/configs/router_eval.md` -> `trace/exploration_tree.yaml`
- `claim:ood176` -> `logic/experiments.md` ->
  `evidence/tables/acrouter_release_summary.csv` ->
  `outputs/acrouter_ood176/ood_metrics.json`
- `claim:baseline-coverage` -> `logic/experiments.md` ->
  `evidence/tables/ood176_baseline_table.md` ->
  `outputs/baselines_ood176/`
- `claim:cost-aware` -> `src/configs/router_eval.md` ->
  `evidence/tables/score_matrix.md`
- `claim:coderouterbench` -> `evidence/tables/score_matrix.md` ->
  `../data/coderouterbench/README.md`

## Reproduction Commands

```bash
python -m unittest discover -s tests
python scripts/run_id.py --output-dir outputs/tmp/id
python scripts/run_acrouter_ood176.py --output-dir outputs/tmp/acrouter_ood176
python scripts/run_baselines_ood176.py --output-dir outputs/tmp/baselines_ood176
python scripts/run_pipeline.py --config configs/eval_pipeline.example.json
```

## Legacy OOD112 Supplement

OOD112 is preserved as a legacy SWE-MiniSandbox supplement for auditability and
backward comparison. Current OOD claims and baseline tables should use OOD176.

## Provenance Tags

- `checked-in-output`: copied from repository reference outputs.
- `derived-index`: compact index or explanation derived from checked-in files.
- `maintainer-note`: scope, constraints, or interpretation note.
