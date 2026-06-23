#!/usr/bin/env python3
"""Download public Hugging Face assets used by this repository."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from acrouter_repro.hf_assets import (  # noqa: E402
    DEFAULT_DATASET_REPO_ID,
    MINIMAL_DATASET_PATTERNS,
    default_dataset_dir,
    download_coderouterbench,
    download_router_model,
    format_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-repo-id",
        default=DEFAULT_DATASET_REPO_ID,
        help="Hugging Face dataset repo id.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset_dir(REPO_ROOT),
        help="Local directory for the CodeRouterBench dataset snapshot.",
    )
    parser.add_argument(
        "--dataset-revision",
        default=None,
        help="Optional dataset revision, branch, tag, or commit SHA.",
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Download only files needed for OOD176 replay instead of the full dataset snapshot.",
    )
    parser.add_argument(
        "--router-model-repo",
        default=None,
        help=(
            "Optional Hugging Face model repo id for a public router adapter. "
            "No public Lance1573 model repo is required for the offline benchmark replay."
        ),
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=REPO_ROOT / ".hf" / "router_model",
        help="Local directory for the optional router model snapshot.",
    )
    parser.add_argument(
        "--model-revision",
        default=None,
        help="Optional model revision, branch, tag, or commit SHA.",
    )
    parser.add_argument("--token", default=None, help="Optional Hugging Face token.")
    parser.add_argument(
        "--hf-max-workers",
        type=int,
        default=1,
        help="Parallel HF download workers. Defaults to 1 for robust CLI behavior.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    layout = download_coderouterbench(
        local_dir=args.dataset_dir,
        repo_id=args.dataset_repo_id,
        revision=args.dataset_revision,
        allow_patterns=MINIMAL_DATASET_PATTERNS if args.minimal else None,
        token=args.token,
        max_workers=args.hf_max_workers,
    )
    print(f"dataset_repo={args.dataset_repo_id}")
    print(f"dataset_dir={format_path(layout.root, REPO_ROOT)}")
    print(f"ood_matrix={format_path(layout.ood_matrix, REPO_ROOT)}")
    print(f"summary={format_path(layout.summary, REPO_ROOT)}")
    print(f"models={format_path(layout.models, REPO_ROOT)}")

    if args.router_model_repo:
        model_dir = download_router_model(
            repo_id=args.router_model_repo,
            local_dir=args.model_dir,
            revision=args.model_revision,
            token=args.token,
            max_workers=args.hf_max_workers,
        )
        print(f"router_model_repo={args.router_model_repo}")
        print(f"router_model_dir={format_path(model_dir, REPO_ROOT)}")
    else:
        print("router_model_repo=skipped")
        print("router_model_note=no public router model repo is required for offline replay")


if __name__ == "__main__":
    main()
