#!/usr/bin/env python3
"""Extract safe patch-only OOD prediction bundles from MiniSandbox outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.predictions import patch_sha256, safe_model_filename  # noqa: E402


PRED_SOURCES = {
    "claude-opus-4-6": "output_mini_claude-opus-4-6_200/preds.json",
    "claude-sonnet-4-6": "output_mini_claude-sonnet-4-6_112/preds.json",
    "gpt-5.4": "output_mini_gpt54_200/preds.json",
    "glm-5": "output_mini_glm-5-ds_112/preds.json",
    "kimi-k2.5": "output_mini_kimi-k2.5-ds_112/preds.json",
    "MiniMax-M2.7": "output_mini_MiniMax-M2.7_112/preds.json",
    "Qwen3-Max": "output_mini_qwen3-max-ds_112/preds.json",
    "qwen3.5-plus": "output_mini_qwen3.5-plus-ds_112/preds.json",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Directory containing local MiniSandbox output_* folders with preds.json files.",
    )
    parser.add_argument("--matrix", type=Path, default=ROOT / "data" / "ood" / "matrix.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "ood" / "predictions")
    args = parser.parse_args()

    matrix = json.load(args.matrix.open())
    wanted_ids = set(matrix["ids"])
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "models": {}, "note": "patch-only bundle; no trajectories or model configs"}

    for model, rel in PRED_SOURCES.items():
        source_path = args.source_root / rel
        with source_path.open() as f:
            preds = json.load(f)
        items = {}
        for task_id in matrix["ids"]:
            raw = preds.get(task_id) or {}
            patch = raw.get("model_patch") or ""
            items[task_id] = {
                "instance_id": task_id,
                "model_name_or_path": model,
                "model_patch": patch,
                "patch_sha256": patch_sha256(patch),
                "patch_non_empty": bool(patch.strip()),
            }
        out_path = args.out / f"{safe_model_filename(model)}.json"
        with out_path.open("w") as f:
            json.dump({"schema_version": 1, "model": model, "items": items}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        manifest["models"][model] = {
            "file": out_path.name,
            "source_file": rel,
            "items": len(items),
            "non_empty": sum(1 for item in items.values() if item["patch_non_empty"]),
            "source_items": len(preds),
            "missing_source_ids": len(wanted_ids - set(preds)),
        }

    with (args.out / "manifest.json").open("w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote patch bundle to {args.out}")


if __name__ == "__main__":
    main()
