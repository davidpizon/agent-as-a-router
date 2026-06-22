#!/usr/bin/env python3
"""Build compact, response-free data files needed by this release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

BACKEND_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "kimi-k2.5",
    "gpt-5.4",
    "MiniMax-M2.7",
    "qwen3.5-plus",
    "glm-5",
    "Qwen3-Max",
]
MODEL_ALIASES = {"Qwen3-Max": "通义千问Max"}
VOTERS = [
    "finetuned_router_qwen35_08b",
    "finetuned_router_qwen35_2b",
    "finetuned_router_qwen35_9b_v3",
    "finetuned_router_qwen35_27b_v3",
    "logreg",
    "tfidf_mlp",
    "routellm_mf",
    "routellm_sw",
    "dimension_best",
]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="coding-router data directory")
    parser.add_argument("--ood-matrix", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    id_out = args.out / "id"
    ood_out = args.out / "ood"
    id_out.mkdir(parents=True, exist_ok=True)
    ood_out.mkdir(parents=True, exist_ok=True)

    shutil.copy2(args.source / "analysis" / "oracle_labels.jsonl", id_out / "oracle_labels.jsonl")
    shutil.copytree(args.source / "routing" / "splits", id_out / "splits", dirs_exist_ok=True)
    shutil.copy2(args.ood_matrix, ood_out / "matrix.json")

    dimensions = []
    for path in sorted((args.source / "processed").glob("*.jsonl")):
        if path.name == "agentic_programming.jsonl":
            continue
        for row in iter_jsonl(path):
            task_id = row.get("task_id")
            if task_id:
                dimensions.append({"task_id": task_id, "dimension": row.get("dimension")})
    write_jsonl(id_out / "task_dimensions.jsonl", dimensions)

    token_rows = []
    for model in BACKEND_MODELS:
        model_dir = args.source / "results" / model
        if not model_dir.exists() and model in MODEL_ALIASES:
            model_dir = args.source / "results" / MODEL_ALIASES[model]
        if not model_dir.exists():
            continue
        for path in sorted(model_dir.glob("*.jsonl")):
            for row in iter_jsonl(path):
                token_rows.append(
                    {
                        "task_id": row["task_id"],
                        "model": model,
                        "input_tokens": int(row.get("input_tokens", 0) or 0),
                        "output_tokens": int(row.get("output_tokens", 0) or 0),
                    }
                )
    write_jsonl(id_out / "tokens.jsonl", token_rows)

    voter_dir = id_out / "voter_decisions"
    voter_dir.mkdir(parents=True, exist_ok=True)
    for voter in VOTERS:
        source_path = args.source / "routing" / "results" / f"{voter}_decisions.jsonl"
        rows = (
            {"task_id": row["task_id"], "chosen_model": row["chosen_model"]}
            for row in iter_jsonl(source_path)
            if row.get("task_id") and row.get("chosen_model")
        )
        write_jsonl(voter_dir / f"{voter}.jsonl", rows)

    print(f"Wrote compact data to {args.out}")


if __name__ == "__main__":
    main()
