# Data Layout

This directory contains the compact data needed to reproduce ACRouter and the
offline baselines.

## Main Data

- `id/`: phase-1 in-distribution data. It contains splits, task dimensions,
  oracle labels, token counts, and saved voter decisions. It intentionally omits
  full model responses and task solutions.
- `matrices/phase1_acrouter_v2/`: phase-1 observation and response matrices.
- `matrices/phase2_ood/`: Old112, New64, and unified OOD176 matrices. OOD176 is
  the current public OOD benchmark in this release.
- `baseline_inputs/`: saved inputs needed to replay trained-policy and published
  baseline decisions on OOD176.

## Legacy Supplement

- `ood/`: legacy OOD112 SWE-MiniSandbox data. It includes the cost/oracle
  matrix, patch-only model submissions, and a hash-checked verifier cache for
  backward comparison.

## Regeneration Scripts

The bundled data is enough for normal reproduction. The following scripts are
only for maintainers who have local raw experiment outputs:

```bash
python scripts/build_compact_data.py --source /path/to/coding-router/data --out data
python scripts/build_ood_patch_bundle.py --source-root /path/to/MiniSandbox
python scripts/build_sandbox_cache.py --source-root /path/to/MiniSandbox
python scripts/build_ood176_dataset.py
```

`build_ood_patch_bundle.py` copies only `instance_id`, `model_name_or_path`,
`model_patch`, and patch hashes. It does not copy trajectories, model configs,
prompts, responses, or API metadata. The sandbox cache is hash-checked against
those patches before cached verification results are reused.
