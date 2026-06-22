# ACRouter

**Project Homepage:** [https://www.omnisource.cn/agent-as-a-router](https://www.omnisource.cn/agent-as-a-router)

ACRouter is an offline-reproducible routing framework for comparing an
agent-style router against single-model, heuristic, online-bandit, retrieval,
and trained-policy baselines on coding tasks.

This release is intentionally self-contained. It includes the code, compact
metrics data, saved baseline checkpoints, OOD matrices, reference outputs, and
tests needed to reproduce the reported tables without API keys or live model
calls.

The current public OOD benchmark in this bundle is **OOD176**. The older
OOD112/SWE-MiniSandbox reproduction is kept only as a legacy supplement and is
documented near the end.

## Quick Start

From a fresh machine or fresh Python environment:

```bash
cd open-source-acrouter

conda create -n acrouter python=3.11 -y
conda activate acrouter

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e .

python -m unittest discover -s tests
```

If the tests pass, run the main reproductions:

```bash
# In-distribution ID reproduction.
python scripts/run_id.py --output-dir outputs/tmp/id

# Current OOD176 ACRouter reproduction.
python scripts/run_acrouter_ood176.py --output-dir outputs/tmp/acrouter_ood176

# All OOD176 baselines and the paper-style table.
python scripts/run_baselines_ood176.py --output-dir outputs/tmp/baselines_ood176

# Custom benchmark/model pipeline example.
python scripts/run_pipeline.py --config configs/eval_pipeline.example.json
```

The commands above write to `outputs/tmp/` so the checked-in reference outputs
are not overwritten. Omit `--output-dir` to regenerate the reference locations
under `outputs/`.

## Expected Outputs

`scripts/run_id.py` should print:

```text
ID n=2919 AvgPerf=50.14 CumReg=201.9 $Total=22.91 Perf/$=2.19 rAcc=0.2395
```

`scripts/run_acrouter_ood176.py` should print:

| split | n | AvgPerf% | CumReg | $Total | Perf/$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| OOD176 | 176 | 73.30 | 14.4 | 68.29 | 1.07 |

`scripts/run_baselines_ood176.py` writes:

- `baseline_table.md`: paper-style table.
- `baseline_table.csv`: same table as CSV.
- `baseline_table.tex`: LaTeX table body.
- `baseline_metrics.json`: full metrics, notes, and source metadata.
- `decisions/*.jsonl`: per-task routing decisions for each baseline.

Checked-in reference files live in `outputs/baselines_ood176/`.

## Add New Models Or Tasks

Use `scripts/run_pipeline.py` when you want to evaluate a new benchmark, a new
model set, or both. The pipeline accepts either:

- a ready-made matrix with the same schema as
  `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json`, or
- `tasks.jsonl` plus `model_results.jsonl`, which the script converts into that
  matrix schema before scoring.

Run the bundled toy example:

```bash
python scripts/run_pipeline.py --config configs/eval_pipeline.example.json
```

The config names models, optional prices, task/result files, and evaluations:

```json
{
  "tasks_path": "../examples/custom_benchmark/tasks.jsonl",
  "results_path": "../examples/custom_benchmark/model_results.jsonl",
  "models": {
    "toy-fast": {"input_per_1m": 5.00, "output_per_1m": 15.00},
    "toy-strong": {"input_per_1m": 100.00, "output_per_1m": 300.00}
  },
  "evaluations": [
    {
      "name": "ACRouter custom cascade",
      "type": "verify_and_escalate",
      "cheap_chain": ["toy-fast"],
      "escalate_to": "toy-strong",
      "k": 1
    },
    {"name": "Always toy-strong", "type": "always", "model": "toy-strong"},
    {"name": "Oracle", "type": "oracle"}
  ]
}
```

`model_results.jsonl` rows should include at least `task_id`, `model`, and
either `resolved` or `score`. Token fields are optional but let the pipeline
compute cost from the config:

```json
{"task_id":"my_task","model":"my_model","resolved":true,"apply_ok":true,"input_tokens":1200,"output_tokens":220}
```

The pipeline writes `matrix.json`, `summary.csv`, `summary.md`,
`metrics/*.json`, and `decisions/*.jsonl` under the configured output directory.
This is the recommended path for adding public benchmark tasks or model results
without touching the built-in OOD176 files.

## Inference Integration

For production or research workflows, import `ACRouter` and provide your own
model caller plus verifier:

```python
from acrouter_repro.inference import ACRouter

router = ACRouter(
    candidate_models=["cheap-model", "strong-model"],
    cheap_chain=["cheap-model"],
    escalate_to="strong-model",
    k=1,
)

decision = router.run_with_verifier(
    task={"task_id": "task_001", "dimension": "bug_fixing", "prompt": "..."},
    call_model=lambda model, task: call_your_backend(model, task),
    verify=lambda response, task, model: run_your_checks(response, task),
)

print(decision.chosen_model, decision.final_response)
```

A complete mock example is available at `examples/inference_demo.py`. Use
`router.route(task)` instead if your workflow wants only the model choice and
will handle execution separately.

## Agentic Artifacts

For automated readers and coding agents, `agentic-artifacts/` provides a compact
research-artifact entry layer over this repository. Start with:

```text
agentic-artifacts/PAPER.md
agentic-artifacts/manifest.json
agentic-artifacts/evidence/tables/score_matrix.md
```

That folder mirrors the important claims, experiment scope, key metrics,
baseline table, matrix pointers, reproduction commands, and design trace using
small Markdown, JSON, YAML, CSV, and HTML files. It does not replace the
canonical data under `data/` or reference outputs under `outputs/`; it points to
them with relative paths so agents can load only the evidence they need.

## Repository Layout

```text
agentic-artifacts/               Agent-readable manifest, claims, evidence map
configs/eval_pipeline.example.json Custom evaluation pipeline example
examples/                         Custom benchmark and inference demos
src/acrouter_repro/              ACRouter reproduction package
src/routing/                     Baseline router implementations
scripts/run_id.py                ID ACRouter entrypoint
scripts/run_acrouter_ood176.py   ACRouter replay on OOD176
scripts/run_baselines_ood176.py  OOD176 baseline replay
scripts/run_pipeline.py          Config-driven custom model/task evaluation
tests/                           Unit and bundle-integrity tests

data/id/                         Phase-1 compact ID labels, splits, tokens
data/ood/                        Legacy OOD112 matrix, patches, verifier cache
data/matrices/phase1_acrouter_v2 Phase-1 observation/response matrices
data/matrices/phase2_ood/        Old112, New64, and unified OOD176 matrices
data/baseline_inputs/            Baseline decisions/checkpoints for OOD176 replay
outputs/                         Checked-in reference outputs
```

The command `python -m pip install -e .` makes `acrouter_repro` importable for
interactive use and downstream workflows. The repository is still script-first:
entrypoints add `src/` to `PYTHONPATH` automatically. If you choose not to
install the package, use:

```bash
export PYTHONPATH="$PWD/src:$PWD"
```

## Data Included

The release keeps only data needed for offline scoring and reproduction.

- `data/id/` contains task dimensions, train/val/test splits, oracle labels,
  token counts, and saved voter decisions. It does not include raw model
  responses or task solutions.
- `data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json` is the unified
  176-task matrix used by the current OOD runs.
- `data/matrices/phase2_ood/raw/new64/matrix.json` records the filtered New64
  subset: FeatureBench 49 + LongCLI 14 + SWE-CI 1. The excluded 8 SWE-CI task
  IDs are recorded in the same JSON file.
- `data/ood/` contains the legacy OOD112 SWE-MiniSandbox matrix, patch-only
  model submissions, and a hash-checked sandbox cache for supplementary
  reproduction.

To rebuild the OOD176 unified matrix from the bundled raw snapshots:

```bash
python scripts/build_ood176_dataset.py
```

## Dependency Sets

`requirements.txt` is the recommended default environment. It covers tests,
ACRouter reproduction, OOD176 baseline replay, saved trained-router checkpoints,
and legacy baseline training utilities.

```bash
python -m pip install -r requirements.txt
```

`requirements-sandbox.txt` extends the default environment with Python packages
needed for live SWE-bench or legacy SWE-MiniSandbox grading. You only need it if
you want to re-run Docker or Apptainer verification instead of using the bundled
hash-checked cache.

```bash
python -m pip install -r requirements-sandbox.txt
```

Live sandbox grading also needs non-Python assets:

- Docker or Apptainer installed on the host.
- SWE-bench Verified parquet data.
- Cached SWE-bench evaluation images or SIF files.

The default cached reproduction does not need those assets.

## Common Commands

Run the cleaned ID reproduction:

```bash
python scripts/run_id.py --output-dir outputs/tmp/id
```

Run the secret scanner:

```bash
bash scripts/check_no_secrets.sh
```

## Legacy OOD112 Supplement

OOD112 is the older SWE-MiniSandbox stream used during development. It remains
in the repository for auditability and backward comparison, but OOD176 is the
current OOD benchmark for public results.

Run the legacy ID + OOD112 summary:

```bash
python scripts/run_all.py --output-dir outputs/tmp/run_all_legacy_ood112
```

Run legacy OOD112 with the bundled report cache:

```bash
python scripts/run_ood_sandbox.py \
  --verifier report-cache \
  --output-dir outputs/tmp/legacy_ood112
```

Run live Docker verification for a legacy OOD112 sandbox-command setup:

```bash
python scripts/run_ood_sandbox.py \
  --verifier sandbox-command \
  --grade-script scripts/grade_swebench_docker.py \
  --dataset-path /path/to/SWE-bench_Verified/data/test-00000-of-00001.parquet \
  --output-dir outputs/tmp/legacy_ood112_live
```

## Notes And Caveats

- No API keys are required. The release does not call external model APIs.
- `RouteLLM-BERT` on OOD176 uses the available legacy RouteLLM-SW OOD112
  decision replay as the closest published proxy for the Old112 portion; this
  matches the recorded experiment note in `baseline_metrics.json`.
- `Qwen3.5-0.8B-Finetuned` on OOD176 uses the available
  legacy `L2_ft08b_router_v3` OOD112 decisions for the Old112 portion and a
  modal New64 extension because no runnable finetuned-router API artifact is
  bundled.
- The saved `bert_mlp_router.pkl` checkpoint uses the TF-IDF fallback path, so
  OOD176 baseline replay does not download a sentence-transformer model.
- `scripts/build_compact_data.py`, `scripts/build_ood_patch_bundle.py`, and
  `scripts/build_sandbox_cache.py` are maintainer scripts for rebuilding compact
  data from raw local experiment outputs. Normal users do not need them.

## Citation

If you use this bundle, please cite the associated arXiv paper. The arXiv ID is
left blank until the preprint is available.

```bibtex
@article{acrouter2026,
  title         = {Agent-as-a-Router},
  author        = {ACRouter Authors},
  journal       = {arXiv preprint arXiv:},
  year          = {2026},
  archivePrefix = {arXiv},
  eprint        = {},
}
```
