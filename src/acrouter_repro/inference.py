"""Workflow-facing ACRouter API.

This module is intentionally small and dependency-free. It lets downstream
systems use ACRouter as a routing component without adopting the benchmark
runner or any model-provider SDK.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .constants import BACKEND_MODELS, OOD_CHEAP_CHAIN, OOD_ESCALATE_TO


@dataclass
class RouteAttempt:
    """One backend model attempt made by an inference workflow."""

    model: str
    resolved: bool = False
    apply_ok: bool = False
    score: float | None = None
    response: Any = None
    feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not isinstance(self.response, (str, int, float, bool, type(None), list, dict)):
            data["response"] = repr(self.response)
        return data


@dataclass
class InferenceDecision:
    """Final routing decision returned to a caller."""

    task_id: str
    chosen_model: str
    candidate_chain: list[str]
    attempts: list[RouteAttempt] = field(default_factory=list)
    escalated: bool = False
    reason: str = ""

    @property
    def final_response(self) -> Any:
        return self.attempts[-1].response if self.attempts else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "chosen_model": self.chosen_model,
            "candidate_chain": self.candidate_chain,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "escalated": self.escalated,
            "reason": self.reason,
        }


class ACRouter:
    """Small ACRouter adapter for arbitrary inference workflows.

    `route()` returns a single model choice when the caller owns execution.
    `run_with_verifier()` owns the full verify-and-escalate loop by accepting
    two user-provided callbacks:

    - `call_model(model, task) -> response`
    - `verify(response, task, model) -> bool | dict`
    """

    def __init__(
        self,
        *,
        candidate_models: list[str] | None = None,
        cheap_chain: list[str] | None = None,
        escalate_to: str | None = None,
        k: int = 2,
        dimension_map: dict[str, str] | None = None,
        default_model: str | None = None,
    ):
        self.cheap_chain = list(cheap_chain or OOD_CHEAP_CHAIN)
        self.escalate_to = escalate_to or OOD_ESCALATE_TO
        self.candidate_models = list(
            candidate_models or _unique(self.cheap_chain + [self.escalate_to] + BACKEND_MODELS)
        )
        self.k = k
        self.dimension_map = dict(dimension_map or {})
        self.default_model = default_model or (self.cheap_chain[0] if self.cheap_chain else self.candidate_models[0])
        self.memory: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._validate()

    def _validate(self) -> None:
        if self.k < 0:
            raise ValueError("k must be non-negative")
        if not self.candidate_models:
            raise ValueError("candidate_models cannot be empty")
        for model in self.cheap_chain + [self.escalate_to, self.default_model]:
            if model not in self.candidate_models:
                raise ValueError(f"router model '{model}' is not in candidate_models")

    def route(self, task: dict[str, Any]) -> InferenceDecision:
        """Choose the next model without executing it."""

        task_id = str(task.get("task_id") or task.get("id") or "unknown")
        dimension = str(task.get("dimension") or task.get("benchmark") or "unknown")
        learned = self._best_memory_model(dimension)
        mapped = self.dimension_map.get(dimension)
        chosen = learned or mapped or self.default_model
        reason = "memory" if learned else "dimension_map" if mapped else "default"
        return InferenceDecision(
            task_id=task_id,
            chosen_model=chosen,
            candidate_chain=[chosen],
            reason=reason,
        )

    def run_with_verifier(
        self,
        task: dict[str, Any],
        call_model: Callable[[str, dict[str, Any]], Any],
        verify: Callable[..., bool | dict[str, Any]],
    ) -> InferenceDecision:
        """Run the full ACRouter verify-and-escalate loop.

        The verifier may return either a boolean or a dict. Dict feedback should
        use `resolved`, `apply_ok`, and optionally `score`.
        """

        task_id = str(task.get("task_id") or task.get("id") or "unknown")
        attempts: list[RouteAttempt] = []
        cheap_apply_count = 0

        for model in self.cheap_chain:
            attempt = self._attempt(task, model, call_model, verify)
            attempts.append(attempt)
            cheap_apply_count += int(attempt.apply_ok)
            self.observe(task, model, attempt.feedback)
            if attempt.resolved:
                return InferenceDecision(
                    task_id=task_id,
                    chosen_model=model,
                    candidate_chain=[a.model for a in attempts],
                    attempts=attempts,
                    escalated=False,
                    reason="resolved_in_cheap_chain",
                )

        escalated = False
        if cheap_apply_count >= self.k and self.escalate_to not in [a.model for a in attempts]:
            escalated = True
            attempt = self._attempt(task, self.escalate_to, call_model, verify)
            attempts.append(attempt)
            self.observe(task, self.escalate_to, attempt.feedback)

        best = max(
            attempts,
            key=lambda a: (
                int(a.resolved),
                a.score if a.score is not None else 0.0,
                int(a.apply_ok),
            ),
        )
        return InferenceDecision(
            task_id=task_id,
            chosen_model=best.model,
            candidate_chain=[a.model for a in attempts],
            attempts=attempts,
            escalated=escalated,
            reason="escalated" if escalated else "cheap_chain_exhausted",
        )

    def observe(self, task: dict[str, Any], model: str, feedback: bool | dict[str, Any]) -> None:
        """Update lightweight routing memory from external workflow feedback."""

        normalized = _normalize_feedback(feedback)
        dimension = str(task.get("dimension") or task.get("benchmark") or "unknown")
        score = normalized.get("score")
        if score is None:
            score = 1.0 if normalized.get("resolved") else 0.0
        self.memory[dimension][model].append(float(score))

    def _best_memory_model(self, dimension: str) -> str | None:
        entries = self.memory.get(dimension) or {}
        if not entries:
            return None
        return max(entries, key=lambda model: sum(entries[model]) / len(entries[model]))

    def _attempt(
        self,
        task: dict[str, Any],
        model: str,
        call_model: Callable[[str, dict[str, Any]], Any],
        verify: Callable[..., bool | dict[str, Any]],
    ) -> RouteAttempt:
        response = call_model(model, task)
        feedback = _call_verify(verify, response, task, model)
        return RouteAttempt(
            model=model,
            resolved=bool(feedback.get("resolved")),
            apply_ok=bool(feedback.get("apply_ok")),
            score=feedback.get("score"),
            response=response,
            feedback=feedback,
        )


def _call_verify(
    verify: Callable[..., bool | dict[str, Any]],
    response: Any,
    task: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    try:
        feedback = verify(response, task, model)
    except TypeError:
        feedback = verify(response, task)
    return _normalize_feedback(feedback)


def _normalize_feedback(feedback: bool | dict[str, Any]) -> dict[str, Any]:
    if isinstance(feedback, bool):
        return {"resolved": feedback, "apply_ok": feedback}
    if not isinstance(feedback, dict):
        raise TypeError("verifier feedback must be bool or dict")
    normalized = dict(feedback)
    normalized["resolved"] = bool(normalized.get("resolved", normalized.get("passed", False)))
    normalized["apply_ok"] = bool(normalized.get("apply_ok", normalized["resolved"]))
    if "score" in normalized and normalized["score"] is not None:
        normalized["score"] = float(normalized["score"])
    return normalized


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

