"""Baseline routers that require no API calls."""
import random

from .base import BACKEND_MODELS, BaseRouter, RoutingDecision


class RandomRouter(BaseRouter):
    """Uniformly random model selection."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "random"

    async def route(self, task: dict) -> RoutingDecision:
        chosen = self._rng.choice(BACKEND_MODELS)
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=chosen,
            confidence=1.0 / len(BACKEND_MODELS),
            reasoning="Random selection",
        )


class AlwaysBestRouter(BaseRouter):
    """Always route to a fixed model (single-model upper bound)."""

    def __init__(self, best_model: str = "claude-sonnet-4-6"):
        self.best_model = best_model

    @property
    def name(self) -> str:
        return f"always_{self.best_model}"

    async def route(self, task: dict) -> RoutingDecision:
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=self.best_model,
            confidence=1.0,
            reasoning=f"Always route to {self.best_model}",
        )


class AlwaysCheapestRouter(BaseRouter):
    """Always route to the cheapest model (cost lower bound)."""

    def __init__(self, cheapest_model: str = "kimi-k2.5"):
        self.cheapest_model = cheapest_model

    @property
    def name(self) -> str:
        return "always_cheapest"

    async def route(self, task: dict) -> RoutingDecision:
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=self.cheapest_model,
            confidence=1.0,
            reasoning=f"Always route to cheapest: {self.cheapest_model}",
        )


class DimensionRouter(BaseRouter):
    """Route based on best model per dimension (computed from training data)."""

    def __init__(self, dimension_map: dict[str, str] | None = None):
        self._dimension_map = dimension_map or {}

    @property
    def name(self) -> str:
        return "dimension_best"

    def set_dimension_map(self, dimension_map: dict[str, str]):
        self._dimension_map = dimension_map

    async def route(self, task: dict) -> RoutingDecision:
        dim = task.get("dimension", "unknown")
        chosen = self._dimension_map.get(dim, BACKEND_MODELS[0])
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=chosen,
            confidence=1.0,
            reasoning=f"Best model for dimension '{dim}': {chosen}",
        )
