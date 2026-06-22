"""Shared constants for the open ACRouter reproduction."""

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

PRICING_TABLE6 = {
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-5.4": (2.5, 15.0),
    "Qwen3-Max": (1.2, 6.0),
    "glm-5": (0.88, 3.22),
    "kimi-k2.5": (0.6, 3.07),
    "qwen3.5-plus": (0.4, 2.4),
    "MiniMax-M2.7": (0.3, 1.2),
}

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
ROUTER_TOKEN_PRICE_PER_M = 0.054
