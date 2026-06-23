"""Shared constants for the open ACRouter reproduction."""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRICING_PATH = _REPO_ROOT / "data" / "matrices" / "phase1_id" / "model_pricing.json"


def _load_pricing_table6() -> dict[str, tuple[float, float]]:
    payload = json.loads(_PRICING_PATH.read_text())
    return {
        model: (float(row["input_per_1m"]), float(row["output_per_1m"]))
        for model, row in payload["models"].items()
    }

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

MODEL_ALIASES = {
    "通义千问Max": "Qwen3-Max",
}

PRICING_TABLE6 = _load_pricing_table6()

ID_VOTERS = [
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

OOD_CHEAP_CHAIN = ["MiniMax-M2.7", "kimi-k2.5", "gpt-5.4", "glm-5"]
OOD_ESCALATE_TO = "claude-opus-4-6"

REWARD_COST_WEIGHT = 0.1
