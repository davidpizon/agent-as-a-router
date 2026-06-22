"""Placeholder routers for future implementation.

These stubs define the interface for routers that will be implemented later:
- FineTunedRouter: Fine-tuned small model (e.g., Qwen2.5-7B with LoRA)
- RouteLLMRouter: RouteLLM framework adapter
- AgentRouter: Agent-based routing (AutoMix-style)
"""
from .base import BaseRouter, RoutingDecision


class FineTunedRouter(BaseRouter):
    """Router using a fine-tuned small model (e.g., Qwen2.5-7B).

    Will be implemented in Phase 4 with:
    - LoRA fine-tuning on training data
    - Input: task metadata + prompt
    - Output: model classification
    """

    def __init__(self, model_path: str = "", base_url: str = "", device: str = "auto"):
        self.model_path = model_path
        self.base_url = base_url
        self.device = device

    @property
    def name(self) -> str:
        return "finetuned"

    async def route(self, task: dict) -> RoutingDecision:
        raise NotImplementedError(
            "FineTunedRouter requires model training. "
            "Use --prepare-finetune to generate training data first."
        )


class RouteLLMRouter(BaseRouter):
    """Adapter for the RouteLLM framework (MF/BERT/Causal variants).

    Will wrap RouteLLM's routing strategies:
    - Matrix Factorization (MF)
    - BERT-based classifier
    - Causal LM router
    """

    def __init__(self, variant: str = "mf"):
        self.variant = variant

    @property
    def name(self) -> str:
        return f"routellm_{self.variant}"

    async def route(self, task: dict) -> RoutingDecision:
        raise NotImplementedError(
            f"RouteLLMRouter ({self.variant}) requires the RouteLLM package. "
            "Install with: pip install routellm"
        )


class AgentRouter(BaseRouter):
    """Agent-based routing (AutoMix-style).

    Will implement a multi-step routing strategy:
    1. Start with cheapest model
    2. Verify output quality
    3. Escalate to stronger model if needed
    """

    def __init__(self, client=None):
        self.client = client

    @property
    def name(self) -> str:
        return "agent"

    async def route(self, task: dict) -> RoutingDecision:
        raise NotImplementedError(
            "AgentRouter requires online model execution. "
            "This router cannot be evaluated offline."
        )
