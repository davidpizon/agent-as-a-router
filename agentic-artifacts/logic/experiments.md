# Experiments

## Benchmark Streams

- CodeRouterBench ID: 9,999 in-distribution coding tasks x 8 backend models
  under `data/coderouterbench/id_results_long.csv`.
- ID reproduction split: the ACRouter ID headline result is evaluated on the
  2,919-task test split.
- OOD176: current public OOD matrix built from Old112 plus filtered New64 under
  `data/coderouterbench/ood176_results_long.csv` and
  `data/matrices/phase2_ood/unified/`.

## Main ACRouter Results

| split | n | AvgPerf% | CumReg | total cost USD | Perf/USD | extra |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ID | 2919 | 50.14 | 201.9 | 22.91 | 2.19 | test split, hierarchical policy |
| OOD176 | 176 | 73.30 | 14.4 | 68.29 | 1.07 | unified Old112 + New64 matrix |

## OOD176 Baseline Coverage

The paper-style baseline table is mirrored at
`evidence/tables/ood176_baseline_table.md`. The full reference output directory
is `outputs/baselines_ood176/` and includes Markdown, CSV, JSON, TeX, and
per-baseline decision JSONL files.

## Custom Pipeline

New models and benchmark tasks can be evaluated without modifying the bundled
OOD176 files:

```bash
python scripts/run_pipeline.py --config configs/eval_pipeline.example.json
```

The config can point either to a complete matrix or to `tasks.jsonl` plus
`model_results.jsonl`. The runner writes a generated matrix, per-router
decisions, metrics JSON files, and summary tables.

## Rebuild Commands

```bash
python scripts/export_coderouterbench.py
python scripts/build_ood176_dataset.py
python scripts/run_id.py --output-dir outputs/tmp/id
python scripts/run_acrouter_ood176.py --output-dir outputs/tmp/acrouter_ood176
python scripts/run_baselines_ood176.py --output-dir outputs/tmp/baselines_ood176
python scripts/run_pipeline.py --config configs/eval_pipeline.example.json
```

## Legacy OOD112 Supplement

OOD112 is the original SWE-MiniSandbox stream with patch-only submissions and a
bundled report-cache verifier under `data/ood/`. It is preserved for backward
comparison, while current public OOD claims should use OOD176.

| split | n | AvgPerf% | CumReg | total cost USD | Perf/USD | extra |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Legacy OOD112 | 112 | 66.96 | 12.8 | 51.70 | 1.30 | report-cache sandbox verifier |

## Bindings

- Main summary: `evidence/tables/acrouter_release_summary.csv`
- Score-matrix schema: `evidence/tables/score_matrix.md`
- Evaluation configuration: `src/configs/router_eval.md`
- Canonical checked-in outputs: `outputs/`
