# Environment

The ACRouter open-source artifact is script-first and offline by default.
Entrypoints add `src/` to `PYTHONPATH` automatically, and the repository root
README contains the primary setup instructions.

## Recommended Runtime

- Python: 3.11
- Default dependencies: `requirements.txt`
- Editable package install: `python -m pip install -e .`
- Optional live sandbox dependencies: `requirements-sandbox.txt`
- Default verification: `python -m unittest discover -s tests`
- Custom pipeline demo: `python scripts/run_pipeline.py --config configs/eval_pipeline.example.json`
- Inference integration demo: `python examples/inference_demo.py`

## Runtime Surface

- Human README: `../README.md`
- Agent root manifest: `PAPER.md`
- Machine-readable manifest: `manifest.json`
- Static artifact page: `index.html`
- Custom pipeline config: `../configs/eval_pipeline.example.json`
- Inference demo: `../examples/inference_demo.py`
- Canonical data: `../data/`
- Canonical outputs: `../outputs/`

## Reproducibility Assumptions

- The default commands use checked-in compact data and reference caches.
- No live model calls are needed for `run_all.py`, `run_acrouter_ood176.py`, or
  `run_baselines_ood176.py`.
- The saved `bert_mlp_router.pkl` checkpoint uses a TF-IDF fallback path for
  bundled OOD176 replay and does not download a sentence-transformer model.
- Live sandbox grading remains possible, but host Docker/Apptainer binaries and
  external benchmark assets are outside the Python requirements files.
