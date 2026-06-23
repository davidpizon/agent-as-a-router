#!/usr/bin/env python3
"""Run the latest bundled ACRouter OOD path on the unified OOD176 matrix."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = REPO_ROOT / "data" / "matrices" / "phase2_ood" / "unified" / "matrix_acrouter_ood176.json"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "acrouter_ood176"
DEFAULT_HF_DATASET_DIR = REPO_ROOT / ".hf" / "CodeRouterBench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=None,
        help="Explicit OOD176 matrix path. Overrides --hf-dataset-dir.",
    )
    parser.add_argument(
        "--hf-dataset-dir",
        type=Path,
        default=None,
        help=(
            "Path to a Hugging Face CodeRouterBench snapshot, for example "
            ".hf/CodeRouterBench after `hf download Lance1573/CodeRouterBench "
            "--repo-type dataset --local-dir .hf/CodeRouterBench`."
        ),
    )
    parser.add_argument(
        "--download-hf",
        action="store_true",
        help="Download the CodeRouterBench dataset snapshot before resolving paths.",
    )
    parser.add_argument(
        "--minimal-hf",
        action="store_true",
        help="With --download-hf, download only files needed for OOD176 replay.",
    )
    parser.add_argument("--hf-dataset-repo-id", default="Lance1573/CodeRouterBench")
    parser.add_argument("--hf-revision", default=None)
    parser.add_argument(
        "--hf-max-workers",
        type=int,
        default=1,
        help="Parallel HF download workers used with --download-hf.",
    )
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

    from acrouter_repro.hf_assets import (  # noqa: WPS433
        MINIMAL_DATASET_PATTERNS,
        download_coderouterbench,
        format_path,
        resolve_ood_matrix,
    )
    from acrouter_repro.ood_repro import run_ood  # noqa: WPS433

    hf_dataset_dir = args.hf_dataset_dir
    if args.download_hf:
        hf_dataset_dir = hf_dataset_dir or DEFAULT_HF_DATASET_DIR
        layout = download_coderouterbench(
            local_dir=hf_dataset_dir,
            repo_id=args.hf_dataset_repo_id,
            revision=args.hf_revision,
            allow_patterns=MINIMAL_DATASET_PATTERNS if args.minimal_hf else None,
            max_workers=args.hf_max_workers,
        )
        hf_dataset_dir = layout.root

    matrix = resolve_ood_matrix(
        repo_root=REPO_ROOT,
        matrix=args.matrix,
        hf_dataset_dir=hf_dataset_dir,
    )

    result = run_ood(matrix, args.output_dir, k=args.k)
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
    print(f"matrix={format_path(matrix, REPO_ROOT)}")


if __name__ == "__main__":
    main()
