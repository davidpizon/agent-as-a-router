#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCAL_ROOT="${ACROUTER_LOCAL_ROOT:-$(cd "$REPO_ROOT/.." && pwd)/Agentic_efficiency}"
ADAPTER_DIR="${ADAPTER_DIR:-$LOCAL_ROOT/coding-router/models/finetuned_router_qwen35_08b_v4/adapter}"
TRAINING_CONFIG="${TRAINING_CONFIG:-$LOCAL_ROOT/coding-router/models/finetuned_router_qwen35_08b_v4/training_config.json}"
METRICS_PATH="${METRICS_PATH:-$LOCAL_ROOT/coding-router/data/routing/results/finetuned_router_qwen35_08b_v4_metrics.json}"

HF_REPO="${1:-${HF_REPO:-Lance1573/acrouter-qwen35-08b-router-lora}}"
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen3.5-0.8B}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Upload ACRouter Qwen 0.8B router LoRA}"
DRY_RUN="${DRY_RUN:-0}"
HF_PRIVATE="${HF_PRIVATE:-0}"

if ! command -v hf >/dev/null 2>&1; then
  echo "Missing 'hf'. Install it with: python -m pip install -U huggingface_hub" >&2
  exit 1
fi

for required in \
  "$ADAPTER_DIR/adapter_config.json" \
  "$ADAPTER_DIR/adapter_model.safetensors" \
  "$ADAPTER_DIR/tokenizer.json" \
  "$ADAPTER_DIR/tokenizer_config.json" \
  "$TRAINING_CONFIG" \
  "$METRICS_PATH"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 1
  fi
done

run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/acrouter_qwen08b_hf.XXXXXX")"
cleanup() {
  if [[ "${KEEP_STAGE:-0}" != "1" ]]; then
    rm -rf "$stage_dir"
  else
    echo "Keeping staging directory: $stage_dir"
  fi
}
trap cleanup EXIT

echo "Adapter source: $ADAPTER_DIR"
echo "Training config: $TRAINING_CONFIG"
echo "Metrics: $METRICS_PATH"
echo "Base model: $BASE_MODEL"
echo "Hugging Face model repo: $HF_REPO"
echo "Staging directory: $stage_dir"

cp -a "$ADAPTER_DIR/adapter_model.safetensors" "$stage_dir/adapter_model.safetensors"
cp -a "$ADAPTER_DIR/tokenizer.json" "$stage_dir/tokenizer.json"
cp -a "$ADAPTER_DIR/tokenizer_config.json" "$stage_dir/tokenizer_config.json"
if [[ -f "$ADAPTER_DIR/chat_template.jinja" ]]; then
  cp -a "$ADAPTER_DIR/chat_template.jinja" "$stage_dir/chat_template.jinja"
fi
cp -a "$METRICS_PATH" "$stage_dir/eval_metrics.json"

python - "$ADAPTER_DIR/adapter_config.json" "$stage_dir/adapter_config.json" "$stage_dir/README.md" "$BASE_MODEL" "$HF_REPO" "$TRAINING_CONFIG" "$METRICS_PATH" "$stage_dir/training_config.json" <<'PY'
import json
import sys
from pathlib import Path

adapter_src = Path(sys.argv[1])
adapter_dst = Path(sys.argv[2])
readme_dst = Path(sys.argv[3])
base_model = sys.argv[4]
hf_repo = sys.argv[5]
training_path = Path(sys.argv[6])
metrics_path = Path(sys.argv[7])
training_dst = Path(sys.argv[8])

adapter_config = json.loads(adapter_src.read_text())
adapter_config["base_model_name_or_path"] = base_model
adapter_dst.write_text(json.dumps(adapter_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

training = json.loads(training_path.read_text())
training["base_model"] = base_model
training_dst.write_text(json.dumps(training, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
metrics = json.loads(metrics_path.read_text())

target_modules = ", ".join(training.get("target_modules", []))
backend_models = ", ".join(training.get("backend_models", []))

readme = f"""---
license: apache-2.0
base_model: {base_model}
library_name: peft
pipeline_tag: text-generation
tags:
  - peft
  - lora
  - qwen
  - qwen3.5
  - code
  - model-routing
  - agent-as-a-router
  - arxiv:2606.22902
datasets:
  - Lance1573/CodeRouterBench
---

# ACRouter Qwen3.5-0.8B Router LoRA

This repository contains the Qwen3.5-0.8B PEFT/LoRA router used by
Agent-as-a-Router for coding-task model selection. It is an adapter, not a
standalone full model. Load it on top of `{base_model}`.

- Project: https://github.com/LanceZPF/agent-as-a-router
- Dataset: https://huggingface.co/datasets/Lance1573/CodeRouterBench
- Paper: https://huggingface.co/papers/2606.22902
- arXiv: https://arxiv.org/abs/2606.22902

## Files

- `adapter_model.safetensors`: LoRA adapter weights.
- `adapter_config.json`: PEFT adapter configuration with base model set to `{base_model}`.
- `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja`: tokenizer assets copied from the training export.
- `training_config.json`: compact training hyperparameters.
- `eval_metrics.json`: ID test metrics for this router.

## Training Summary

- Base model: `{base_model}`
- PEFT type: `{adapter_config.get("peft_type", "LORA")}`
- LoRA rank: `{training.get("lora_rank", adapter_config.get("r", ""))}`
- LoRA alpha: `{training.get("lora_alpha", adapter_config.get("lora_alpha", ""))}`
- LoRA dropout: `{training.get("lora_dropout", adapter_config.get("lora_dropout", ""))}`
- Target modules: {target_modules}
- Epochs: `{training.get("epochs", "")}`
- Learning rate: `{training.get("lr", "")}`
- Max sequence length: `{training.get("max_length", "")}`
- Training samples: `{training.get("train_samples", "")}`
- Backend model choices: {backend_models}

## Evaluation

Evaluated on the CodeRouterBench ID test split (`n={metrics.get("n_tasks", "")}`):

| metric | value |
| --- | ---: |
| Avg performance | {metrics.get("avg_performance", 0):.6f} |
| Oracle performance | {metrics.get("oracle_performance", 0):.6f} |
| Oracle gap | {metrics.get("oracle_gap", 0):.6f} |
| Routing accuracy | {metrics.get("routing_accuracy", 0):.6f} |
| rAcc | {metrics.get("rAcc", 0):.6f} |
| Strong model call rate | {metrics.get("strong_model_call_rate", 0):.6f} |
| Perf/cost ratio | {metrics.get("perf_cost_ratio", 0):.6f} |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model = "{base_model}"
adapter_id = "{hf_repo}"

tokenizer = AutoTokenizer.from_pretrained(adapter_id, trust_remote_code=True)
base = AutoModelForCausalLM.from_pretrained(
    base_model,
    torch_dtype="auto",
    device_map="auto",
    trust_remote_code=True,
)
model = PeftModel.from_pretrained(base, adapter_id)
model.eval()
```

The adapter is intended for model-routing prompts from Agent-as-a-Router rather
than general-purpose instruction following.

## Limitations

This is a task-specific router trained for selecting among the backend models
listed above. It should not be interpreted as a general coding assistant. The
adapter does not include private API keys, raw trajectories, optimizer states,
or training checkpoints.

## Citation

```bibtex
@article{{agent2026zhou,
  title         = {{Agent-as-a-Router: Agentic Model Routing for Coding Tasks}},
  author        = {{Pengfei Zhou, Zhiwei Tang, Yixing Ma, Jiasheng Tang, Yizeng Han, Zhenglin Wan, Fanqing Meng, Wei Wang, Bohan Zhuang, Wangbo Zhao, Yang You}},
  journal       = {{arXiv preprint arXiv:2606.22902}},
  year          = {{2026}},
  archivePrefix = {{arXiv}},
  eprint        = {{2606.22902}},
  url           = {{https://arxiv.org/abs/2606.22902}},
}}
```
"""

readme_dst.write_text(readme)
PY

echo "Staged model files:"
find "$stage_dir" -maxdepth 1 -type f -printf '  %f %s bytes\n' | sort

repo_args=(hf repo create "$HF_REPO" --type model --exist-ok)
if [[ "$HF_PRIVATE" == "1" ]]; then
  repo_args+=(--private)
fi
run "${repo_args[@]}"
run hf upload "$HF_REPO" "$stage_dir" . \
  --repo-type model \
  --delete "*" \
  --commit-message "$COMMIT_MESSAGE"

echo "Done: https://huggingface.co/$HF_REPO"
