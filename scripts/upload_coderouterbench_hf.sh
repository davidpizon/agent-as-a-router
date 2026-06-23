#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

HF_REPO="${1:-${HF_REPO:-Lance1573/CodeRouterBench}}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Refresh CodeRouterBench dataset}"
DRY_RUN="${DRY_RUN:-0}"

if ! command -v hf >/dev/null 2>&1; then
  echo "Missing 'hf'. Install it with: python -m pip install -U huggingface_hub" >&2
  exit 1
fi

run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/coderouterbench_hf.XXXXXX")"
cleanup() {
  if [[ "${KEEP_STAGE:-0}" != "1" ]]; then
    rm -rf "$stage_dir"
  else
    echo "Keeping staging directory: $stage_dir"
  fi
}
trap cleanup EXIT

echo "Repository root: $REPO_ROOT"
echo "Hugging Face dataset repo: $HF_REPO"
echo "Staging directory: $stage_dir"

run python scripts/export_coderouterbench.py

mkdir -p "$stage_dir"
cp -a data/coderouterbench/. "$stage_dir/"

mkdir -p "$stage_dir/raw_matrices"
cp -a data/matrices/. "$stage_dir/raw_matrices/"

mkdir -p "$stage_dir/outputs"
cp -a outputs/. "$stage_dir/outputs/"
rm -rf "$stage_dir/outputs/tmp"

mkdir -p "$stage_dir/evidence"
cp -a agentic-artifacts/evidence/. "$stage_dir/evidence/"

mkdir -p "$stage_dir/configs"
cp -a configs/eval_pipeline.example.json "$stage_dir/configs/eval_pipeline.example.json"

mkdir -p "$stage_dir/examples"
cp -a examples/custom_benchmark "$stage_dir/examples/custom_benchmark"

echo "Staged top-level layout:"
find "$stage_dir" -maxdepth 1 -mindepth 1 -printf '  %f\n' | sort
echo "Total staged files: $(find "$stage_dir" -type f | wc -l | tr -d ' ')"

run hf repo create "$HF_REPO" --type dataset --exist-ok
run hf upload "$HF_REPO" "$stage_dir" . \
  --repo-type dataset \
  --delete "*" \
  --commit-message "$COMMIT_MESSAGE"

echo "Done: https://huggingface.co/datasets/$HF_REPO"
