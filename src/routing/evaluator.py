"""Router evaluation metrics."""
from dataclasses import dataclass, field, asdict
from typing import Optional

from .base import BACKEND_MODELS, STRONG_MODELS, RoutingDecision
from .data_manager import DataManager


@dataclass
class RouterMetrics:
    # Core performance
    avg_performance: float = 0.0
    oracle_performance: float = 0.0
    oracle_gap: float = 0.0
    oracle_gap_pct: float = 0.0
    routing_accuracy: float = 0.0

    # Cost
    avg_total_tokens: float = 0.0
    avg_router_tokens: float = 0.0
    avg_backend_tokens: float = 0.0

    # Efficiency
    perf_cost_ratio: float = 0.0
    strong_model_call_rate: float = 0.0

    # Metadata
    n_tasks: int = 0
    per_dimension: dict = field(default_factory=dict)
    model_distribution: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class RouterEvaluator:
    """Evaluate router decisions against oracle ground truth."""

    def __init__(self, data_manager: DataManager):
        self.dm = data_manager

    def evaluate(
        self,
        decisions: list[RoutingDecision],
        split: str = "test",
    ) -> RouterMetrics:
        """Compute all metrics in a single pass over decisions."""
        split_ids = set(self.dm.get_split(split))
        # Filter decisions to only those in the requested split
        valid = [d for d in decisions if d.task_id in split_ids]

        if not valid:
            return RouterMetrics()

        total_perf = 0.0
        total_oracle_perf = 0.0
        total_router_tokens = 0
        total_backend_tokens = 0
        correct = 0
        strong_calls = 0  # calls to expensive models (STRONG_MODELS)
        model_counts: dict[str, int] = {m: 0 for m in BACKEND_MODELS}
        dim_stats: dict[str, dict] = {}  # dimension -> {perf_sum, oracle_sum, count}

        for d in valid:
            # Performance
            perf = self.dm.get_score(d.task_id, d.chosen_model)
            if perf is None:
                perf = 0.0
            oracle_model = self.dm.get_oracle_model(d.task_id)
            oracle_perf = self.dm.get_oracle_score(d.task_id)
            if oracle_perf is None:
                oracle_perf = 0.0
            total_perf += perf
            total_oracle_perf += oracle_perf

            # Accuracy
            if d.chosen_model == oracle_model:
                correct += 1

            # Tokens
            router_tok = d.router_input_tokens + d.router_output_tokens
            backend = self.dm.get_backend_tokens(d.task_id, d.chosen_model)
            backend_tok = backend["input_tokens"] + backend["output_tokens"]
            total_router_tokens += router_tok
            total_backend_tokens += backend_tok

            # Model distribution
            if d.chosen_model in model_counts:
                model_counts[d.chosen_model] += 1
            if d.chosen_model in STRONG_MODELS:
                strong_calls += 1

            # Per-dimension
            task = self.dm.get_task(d.task_id)
            dim = task.get("dimension", "unknown") if task else "unknown"
            if dim not in dim_stats:
                dim_stats[dim] = {"perf_sum": 0.0, "oracle_sum": 0.0, "count": 0, "correct": 0}
            dim_stats[dim]["perf_sum"] += perf
            dim_stats[dim]["oracle_sum"] += oracle_perf
            dim_stats[dim]["count"] += 1
            if d.chosen_model == oracle_model:
                dim_stats[dim]["correct"] += 1

        n = len(valid)
        avg_perf = total_perf / n
        avg_oracle = total_oracle_perf / n
        avg_router_tok = total_router_tokens / n
        avg_backend_tok = total_backend_tokens / n
        avg_total_tok = avg_router_tok + avg_backend_tok

        per_dim = {}
        for dim, stats in dim_stats.items():
            c = stats["count"]
            per_dim[dim] = {
                "avg_performance": stats["perf_sum"] / c,
                "oracle_performance": stats["oracle_sum"] / c,
                "oracle_gap": (stats["oracle_sum"] - stats["perf_sum"]) / c,
                "routing_accuracy": stats["correct"] / c,
                "n_tasks": c,
            }

        return RouterMetrics(
            avg_performance=avg_perf,
            oracle_performance=avg_oracle,
            oracle_gap=avg_oracle - avg_perf,
            oracle_gap_pct=((avg_oracle - avg_perf) / avg_oracle * 100) if avg_oracle > 0 else 0.0,
            routing_accuracy=correct / n,
            avg_total_tokens=avg_total_tok,
            avg_router_tokens=avg_router_tok,
            avg_backend_tokens=avg_backend_tok,
            perf_cost_ratio=(avg_perf / avg_total_tok * 1e6) if avg_total_tok > 0 else 0.0,
            strong_model_call_rate=strong_calls / n,
            n_tasks=n,
            per_dimension=per_dim,
            model_distribution={m: c / n for m, c in model_counts.items()},
        )
