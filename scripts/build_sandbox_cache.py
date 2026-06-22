#!/usr/bin/env python3
"""Build a hash-checked verifier cache from MiniSandbox grading reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.predictions import load_model_predictions, patch_sha256, safe_model_filename  # noqa: E402
from acrouter_repro.sandbox_verifier import summarize_tests  # noqa: E402


REPORT_SOURCES = {
    "claude-opus-4-6": "logs/grading_opus_regrade/report.json",
    "claude-sonnet-4-6": "logs/grading_sonnet_regrade/report.json",
    "gpt-5.4": "logs/grading_mini_gpt54_200/report.json",
    "glm-5": "logs/grading_mini_glm-5-ds_112/report.json",
    "kimi-k2.5": "logs/grading_mini_kimi-k2.5-ds_112/report.json",
    "MiniMax-M2.7": "logs/grading_mini_MiniMax-M2.7_112/report.json",
    "Qwen3-Max": "logs/grading_mini_qwen3-max-ds_112/report.json",
    "qwen3.5-plus": "logs/grading_mini_qwen3.5-plus-ds_112/report.json",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Directory containing local MiniSandbox grading report.json files.",
    )
    parser.add_argument("--matrix", type=Path, default=ROOT / "data" / "ood" / "matrix.json")
    parser.add_argument("--predictions-root", type=Path, default=ROOT / "data" / "ood" / "predictions")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "ood" / "sandbox_cache")
    args = parser.parse_args()

    matrix = json.load(args.matrix.open())
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "models": {}, "note": "hash-checked cache built from sandbox report.json files"}

    for model, rel in REPORT_SOURCES.items():
        report_path = args.source_root / rel
        with report_path.open() as f:
            report = json.load(f)
        predictions = load_model_predictions(args.predictions_root, model)
        items = {}
        for task_id in matrix["ids"]:
            raw = report.get(task_id)
            if not isinstance(raw, dict):
                continue
            patch = predictions.get(task_id, {}).get("model_patch") or ""
            report_payload = raw.get("report") if isinstance(raw.get("report"), dict) else raw
            apply_ok = bool(raw.get("apply_ok", report_payload.get("patch_successfully_applied", False)))
            items[task_id] = {
                "instance_id": task_id,
                "model": model,
                "patch_sha256": patch_sha256(patch),
                "resolved": bool(raw.get("resolved", report_payload.get("resolved", False))),
                "apply_ok": apply_ok,
                "patch_non_empty": bool(patch.strip()),
                "error": raw.get("error"),
                "elapsed_s": float(raw.get("elapsed_s", 0.0) or 0.0),
                "tests": summarize_tests(raw),
            }
        out_path = args.out / f"{safe_model_filename(model)}.json"
        with out_path.open("w") as f:
            json.dump({"schema_version": 1, "model": model, "items": items}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        manifest["models"][model] = {
            "file": out_path.name,
            "source_file": rel,
            "items": len(items),
            "resolved": sum(1 for item in items.values() if item["resolved"]),
            "apply_ok": sum(1 for item in items.values() if item["apply_ok"]),
        }

    with (args.out / "manifest.json").open("w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote sandbox cache to {args.out}")


if __name__ == "__main__":
    main()
