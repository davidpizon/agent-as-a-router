#!/usr/bin/env python3
"""Run OOD routing using a sandbox verifier instead of matrix labels."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.ood_sandbox import run_ood_sandbox  # noqa: E402
from acrouter_repro.sandbox_verifier import ReportCacheVerifier, SandboxCommandVerifier  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=ROOT / "data" / "ood" / "matrix.json")
    parser.add_argument("--predictions-root", type=Path, default=ROOT / "data" / "ood" / "predictions")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "sandbox")
    parser.add_argument("--k", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--verifier", choices=["report-cache", "sandbox-command"], default="report-cache")
    parser.add_argument("--sandbox-cache", type=Path, default=ROOT / "data" / "ood" / "sandbox_cache")
    parser.add_argument("--command-work-root", type=Path, default=ROOT / "outputs" / "sandbox_command_work")
    parser.add_argument("--command-template", default=None)
    parser.add_argument("--grade-script", type=Path, default=None)
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--sif-cache", type=Path, default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--eval-timeout", type=int, default=1200)
    parser.add_argument("--command-timeout", type=int, default=1800)
    args = parser.parse_args()

    if args.verifier == "report-cache":
        verifier = ReportCacheVerifier(args.sandbox_cache)
    else:
        verifier = SandboxCommandVerifier(
            work_root=args.command_work_root,
            command_template=args.command_template,
            grade_script=args.grade_script,
            dataset_path=args.dataset_path,
            sif_cache=args.sif_cache,
            python_executable=args.python,
            eval_timeout=args.eval_timeout,
            command_timeout=args.command_timeout,
        )

    result = run_ood_sandbox(
        args.matrix,
        args.predictions_root,
        args.output_dir,
        verifier,
        k=args.k,
        limit=args.limit,
    )
    metrics = result["metrics"]
    print(
        "OOD-sandbox "
        f"n={metrics['n']} "
        f"AvgPerf={metrics['AvgPerf%']:.2f} "
        f"CumReg={metrics['CumReg']:.1f} "
        f"$Total={metrics['$Total']:.2f} "
        f"Perf/$={metrics['Perf/$']:.2f} "
        f"rAcc={metrics['rAcc_reward_oracle']:.4f} "
        f"Apply_ok={metrics['Apply_ok%']:.2f} "
        f"Escalations={metrics['Escalations']} "
        f"AvgSteps={metrics['AvgSteps']:.2f} "
        f"source={metrics['decision_source']} "
        f"verifier={metrics['verifier_mode']}"
    )
    print(f"decisions={args.output_dir / 'ood_sandbox_decisions.jsonl'}")


if __name__ == "__main__":
    main()

