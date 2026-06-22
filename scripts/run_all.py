#!/usr/bin/env python3
"""Run ID and OOD reproductions and write a combined report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.id_repro import run_id  # noqa: E402
from acrouter_repro.ood_repro import run_ood  # noqa: E402
from acrouter_repro.ood_sandbox import run_ood_sandbox  # noqa: E402
from acrouter_repro.report import write_summary  # noqa: E402
from acrouter_repro.sandbox_verifier import ReportCacheVerifier  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id-data-root", type=Path, default=ROOT / "data" / "id")
    parser.add_argument("--ood-matrix", type=Path, default=ROOT / "data" / "ood" / "matrix.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "current")
    parser.add_argument("--id-tune-split", default="val", choices=["train", "val", "test"])
    parser.add_argument("--id-eval-split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--id-policy", default="hierarchical", choices=["hierarchical", "voter"])
    parser.add_argument("--ood-k", type=int, default=2)
    parser.add_argument("--ood-mode", choices=["sandbox-cache", "oracle-matrix"], default="sandbox-cache")
    parser.add_argument("--ood-predictions-root", type=Path, default=ROOT / "data" / "ood" / "predictions")
    parser.add_argument("--ood-sandbox-cache", type=Path, default=ROOT / "data" / "ood" / "sandbox_cache")
    args = parser.parse_args()

    id_result = run_id(
        args.id_data_root,
        args.output_dir,
        tune_split=args.id_tune_split,
        eval_split=args.id_eval_split,
        policy=args.id_policy,
    )
    if args.ood_mode == "sandbox-cache":
        ood_result = run_ood_sandbox(
            args.ood_matrix,
            args.ood_predictions_root,
            args.output_dir,
            ReportCacheVerifier(args.ood_sandbox_cache),
            k=args.ood_k,
        )
    else:
        ood_result = run_ood(args.ood_matrix, args.output_dir, k=args.ood_k)
    text = write_summary(args.output_dir, id_result["metrics"], ood_result["metrics"])
    print(text)


if __name__ == "__main__":
    main()
