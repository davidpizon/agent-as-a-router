#!/usr/bin/env python3
"""Run a config-driven ACRouter evaluation pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "eval_pipeline.example.json",
        help="Pipeline JSON config. May point to a matrix or task/result JSONL files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory override.",
    )
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

    from acrouter_repro.pipeline import run_pipeline  # noqa: WPS433

    output_dir = args.output_dir.resolve() if args.output_dir is not None else None
    result = run_pipeline(args.config, output_dir)
    print(f"output_dir={result['output_dir']}")
    print(f"matrix={result['matrix']}")
    print("")
    print("| router | n | AvgPerf% | CumReg | $Total | Perf/$ | Apply_ok% |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in result["summary"]:
        print(
            "| {router} | {n} | {avg:.2f} | {reg:.1f} | {cost:.2f} | {perf:.2f} | {apply:.2f} |".format(
                router=row["router"],
                n=row["n"],
                avg=row["AvgPerf%"],
                reg=row["CumReg"],
                cost=row["$Total"],
                perf=row["Perf/$"],
                apply=row["Apply_ok%"],
            )
        )


if __name__ == "__main__":
    main()
