#!/usr/bin/env python3
"""Run the OOD ACRouter reproduction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.ood_repro import run_ood  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=ROOT / "data" / "ood" / "matrix.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "current")
    parser.add_argument("--k", type=int, default=2)
    args = parser.parse_args()

    result = run_ood(args.matrix, args.output_dir, args.k)
    metrics = result["metrics"]
    print(
        "OOD "
        f"n={metrics['n']} "
        f"AvgPerf={metrics['AvgPerf%']:.2f} "
        f"CumReg={metrics['CumReg']:.1f} "
        f"$Total={metrics['$Total']:.2f} "
        f"Perf/$={metrics['Perf/$']:.2f} "
        f"rAcc={metrics['rAcc_reward_oracle']:.4f} "
        f"Apply_ok={metrics['Apply_ok%']:.2f} "
        f"Escalations={metrics['Escalations']} "
        f"AvgSteps={metrics['AvgSteps']:.2f}"
    )
    print(f"decisions={args.output_dir / 'ood_decisions.jsonl'}")


if __name__ == "__main__":
    main()
