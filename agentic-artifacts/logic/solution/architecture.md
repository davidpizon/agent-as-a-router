# ACRouter Architecture

ACRouter is organized as a Context-Action-Feedback loop for coding-task model
selection.

## Components

- Context: task metadata, split information, token estimates, matrix entries,
  verifier cache, and historical observations.
- Action: model or cascade decision selected by the router for a task.
- Feedback: observed score, apply status, cost, regret contribution, and
  sandbox/report-cache signals.
- Memory: compact checked-in matrices and decision files that make the offline
  replay deterministic.

## Reproducible Surfaces

- `src/acrouter_repro/`: ACRouter reproduction package for ID, current OOD176,
  and legacy OOD112 replay.
- `src/routing/`: baseline router implementations and saved-checkpoint loaders.
- `scripts/run_id.py`: ID entrypoint.
- `scripts/run_acrouter_ood176.py`: ACRouter replay on the unified OOD176
  matrix.
- `scripts/run_baselines_ood176.py`: OOD176 baseline replay and table writer.
- `scripts/run_pipeline.py`: config-driven custom model/task evaluation.
- `src/acrouter_repro/inference.py`: importable ACRouter API for arbitrary
  inference workflows.
- `examples/inference_demo.py`: minimal workflow integration demo.

## Cross-Layer Bindings

- Claims: `logic/claims.md`
- Evaluation config: `src/configs/router_eval.md`
- Trace graph: `trace/exploration_tree.yaml`
- Evidence: `evidence/tables/score_matrix.md`
