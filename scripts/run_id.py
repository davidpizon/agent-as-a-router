#!/usr/bin/env python3
"""Run the ID ACRouter reproduction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.id_repro import run_id  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "id")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "current")
    parser.add_argument("--tune-split", default="val", choices=["train", "val", "test"])
    parser.add_argument("--eval-split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--policy", default="hierarchical", choices=["hierarchical", "voter"])
    args = parser.parse_args()

    result = run_id(args.data_root, args.output_dir, args.tune_split, args.eval_split, policy=args.policy)
    metrics = result["metrics"]
    print(
        "ID "
        f"n={metrics['n']} "
        f"AvgPerf={metrics['AvgPerf%']:.2f} "
        f"CumReg={metrics['CumReg']:.1f} "
        f"$Total={metrics['$Total']:.2f} "
        f"Perf/$={metrics['Perf/$']:.2f} "
        f"rAcc={metrics['rAcc_perf_oracle']:.4f} "
        f"missing_score={metrics['missing_score']} "
        f"policy={metrics['policy']} "
        f"tune={metrics['tune_split']} "
        f"eval={metrics['eval_split']} "
        f"leakage={metrics['leakage_risk']}"
    )
    print(f"selection={args.output_dir / 'id_selection.json'}")
    print(f"decisions={args.output_dir / 'id_decisions.jsonl'}")


if __name__ == "__main__":
    main()
