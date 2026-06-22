#!/usr/bin/env python3
"""Run the latest bundled ACRouter OOD path on the unified OOD176 matrix."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = REPO_ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "matrix_acrouter_ood176.json"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "acrouter_ood176"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--k", type=int, default=2)
    parser.add_argument("--expected-n", type=int, default=176)
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=REPO_ROOT / "src",
        help="Repository src directory containing the acrouter_repro package.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.src_dir.exists():
        raise FileNotFoundError(f"ACRouter src directory not found: {args.src_dir}")
    sys.path.insert(0, str(args.src_dir))

    from acrouter_repro.ood_repro import run_ood  # noqa: WPS433

    result = run_ood(args.matrix, args.output_dir, k=args.k)
    metrics = result["metrics"]
    n = int(metrics.get("n", 0))
    if args.expected_n is not None and n != args.expected_n:
        raise RuntimeError(f"expected n={args.expected_n}, got n={n}")

    print(
        "ACRouter-OOD176 "
        f"n={n} "
        f"AvgPerf={metrics['AvgPerf%']:.2f} "
        f"CumReg={metrics['CumReg']:.1f} "
        f"$Total={metrics['$Total']:.2f} "
        f"Perf/$={metrics['Perf/$']:.2f} "
        f"rAcc={metrics['rAcc_reward_oracle']:.4f} "
        f"Apply_ok={metrics['Apply_ok%']:.2f} "
        f"Escalations={metrics['Escalations']} "
        f"AvgSteps={metrics['AvgSteps']:.2f}"
    )
    print(f"metrics={args.output_dir / 'ood_metrics.json'}")
    print(f"decisions={args.output_dir / 'ood_decisions.jsonl'}")


if __name__ == "__main__":
    main()
