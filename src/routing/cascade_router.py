"""Cascade router using heuristic rules based on Phase 2 analysis.

Routes based on dimension + difficulty, with hard-task upgrade to stronger model.
No API calls — pure heuristic.
"""
from .base import BACKEND_MODELS, BaseRouter, RoutingDecision
from .data_manager import DataManager


# Heuristic dimension->model mapping based on Phase 2 routing_analysis.json (8-model)
# These are the best models per dimension among all 8 backend models
_DEFAULT_DIMENSION_MAP = {
    "code_generation": "claude-opus-4-6",    # opus 0.317 best among scored models
    "algorithm": "qwen3.5-plus",             # qwen 0.748, dramatically best
    "bug_fixing": "claude-sonnet-4-6",       # all ~0, default to sonnet
    "code_completion": "claude-sonnet-4-6",  # sonnet 0.713 vs opus 0.709
    "code_refactoring": "claude-opus-4-6",   # opus 0.001 vs others ~0
    "data_science": "claude-sonnet-4-6",     # sonnet 0.220, clearly best
    "multi_language": "claude-opus-4-6",     # opus 0.169 vs sonnet 0.165
    "code_understanding": "MiniMax-M2.7",    # MiniMax 0.011 vs opus 0.009
    "test_generation": "claude-opus-4-6",    # opus 0.515, clearly best
}

# Dimensions where task difficulty matters significantly
_HIGH_ROUTING_VALUE_DIMS = {"algorithm", "code_completion", "data_science", "test_generation"}


class CascadeRouter(BaseRouter):
    """Heuristic cascade: route by dimension, upgrade hard tasks to stronger model."""

    def __init__(
        self,
        data_manager: DataManager | None = None,
        dimension_map: dict[str, str] | None = None,
        strong_model: str = "claude-opus-4-6",
        upgrade_hard: bool = True,
    ):
        self.dm = data_manager
        self._dimension_map = dimension_map or _DEFAULT_DIMENSION_MAP
        self.strong_model = strong_model
        self.upgrade_hard = upgrade_hard

    @property
    def name(self) -> str:
        return "cascade_heuristic"

    async def initialize(self):
        """Optionally learn dimension map from training data."""
        if self.dm:
            learned = self.dm.get_dimension_best_models()
            # Only override defaults where we have training data
            for dim, model in learned.items():
                self._dimension_map[dim] = model

    async def route(self, task: dict) -> RoutingDecision:
        dim = task.get("dimension", "unknown")
        difficulty = task.get("difficulty", "unknown")

        # Base choice: best model for this dimension
        chosen = self._dimension_map.get(dim, BACKEND_MODELS[0])
        reasoning = f"Dimension '{dim}' -> {chosen}"

        # Upgrade: if task is hard and in a high-routing-value dimension,
        # and the default choice isn't already the strong model, upgrade
        if (
            self.upgrade_hard
            and difficulty == "hard"
            and dim in _HIGH_ROUTING_VALUE_DIMS
            and chosen != self.strong_model
        ):
            chosen = self.strong_model
            reasoning += f" (upgraded to {self.strong_model} for hard task)"

        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=chosen,
            confidence=1.0,
            reasoning=reasoning,
        )
