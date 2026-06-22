"""Base classes for the routing framework."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional
import json

BACKEND_MODELS = [
    "claude-sonnet-4-6", "claude-opus-4-6", "kimi-k2.5",
    "gpt-5.4", "MiniMax-M2.7", "qwen3.5-plus", "glm-5",
    "Qwen3-Max",
]

# Mapping from canonical names (BACKEND_MODELS) to data-file names.
# Data files (oracle_labels.jsonl, results/, configs/) may use legacy names.
MODEL_DATA_ALIASES = {
    "Qwen3-Max": "通义千问Max",
}
# Reverse mapping: data-file name -> canonical name
MODEL_DATA_REVERSE = {v: k for k, v in MODEL_DATA_ALIASES.items()}

# Models considered "strong/expensive" — used for strong_model_call_rate metric
STRONG_MODELS = {"claude-opus-4-6", "gpt-5.4"}

# Fields that the router should never see (answers to the task)
SANITIZE_FIELDS = {"canonical_solution", "test_cases", "entry_point"}


@dataclass
class RoutingDecision:
    task_id: str
    chosen_model: str
    confidence: float = 1.0
    router_input_tokens: int = 0
    router_output_tokens: int = 0
    router_latency_ms: int = 0
    reasoning: str = ""

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class BaseRouter(ABC):
    """Abstract base class for all routers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable router name."""
        ...

    @abstractmethod
    async def route(self, task: dict) -> RoutingDecision:
        """Route a task to a backend model.

        Args:
            task: dict with keys including 'task_id', 'prompt' (original problem text),
                  'dimension', 'difficulty', 'language'. Ground-truth fields are stripped
                  by _sanitize_task().

        Returns:
            RoutingDecision with chosen_model and metadata.
        """
        ...

    async def initialize(self):
        """Optional setup (load models, connect to APIs, etc.)."""
        pass

    async def close(self):
        """Optional teardown."""
        pass

    @staticmethod
    def _sanitize_task(task: dict) -> dict:
        """Remove fields the router should not see."""
        return {k: v for k, v in task.items() if k not in SANITIZE_FIELDS}

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.close()
