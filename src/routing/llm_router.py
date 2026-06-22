"""LLM-based routers using an LLM to decide which backend model to use."""
import json
import random
import re
import time

from .base import BACKEND_MODELS, BaseRouter, RoutingDecision
from .data_manager import DataManager
from .prompts import ROUTER_SYSTEM_PROMPT, build_zero_shot_prompt, build_few_shot_prompt


class LLMZeroShotRouter(BaseRouter):
    """Zero-shot LLM router: asks an LLM to pick the best model for each task."""

    def __init__(self, client, router_model: str = "claude-sonnet-4-6"):
        self.client = client
        self.router_model = router_model

    @property
    def name(self) -> str:
        return f"llm_zero_shot_{self.router_model.split('-')[0]}"

    async def route(self, task: dict) -> RoutingDecision:
        sanitized = self._sanitize_task(task)
        prompt = build_zero_shot_prompt(sanitized)

        start = time.monotonic()
        response = await self.client.complete(
            self.router_model, prompt, system_prompt=ROUTER_SYSTEM_PROMPT
        )
        latency = int((time.monotonic() - start) * 1000)

        if response.error:
            # Fallback to default model on error
            return RoutingDecision(
                task_id=task["task_id"],
                chosen_model=BACKEND_MODELS[0],
                confidence=0.0,
                router_input_tokens=response.input_tokens,
                router_output_tokens=response.output_tokens,
                router_latency_ms=latency,
                reasoning=f"Error: {response.error}, falling back to {BACKEND_MODELS[0]}",
            )

        chosen, reasoning = _parse_response(response.text)
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=chosen,
            confidence=1.0,
            router_input_tokens=response.input_tokens,
            router_output_tokens=response.output_tokens,
            router_latency_ms=latency,
            reasoning=reasoning,
        )


class LLMFewShotRouter(BaseRouter):
    """Few-shot LLM router: includes training examples in the prompt."""

    def __init__(
        self,
        client,
        data_manager: DataManager,
        router_model: str = "claude-sonnet-4-6",
        n_shots: int = 3,
    ):
        self.client = client
        self.dm = data_manager
        self.router_model = router_model
        self.n_shots = n_shots
        self._examples_by_dim: dict[str, list[dict]] = {}
        self._rng = random.Random(42)

    @property
    def name(self) -> str:
        return f"llm_{self.n_shots}shot_{self.router_model.split('-')[0]}"

    async def initialize(self):
        """Pre-compute example pools per dimension from training data."""
        # Only use training tasks where models have different scores (routing matters)
        for task_id in self.dm.train:
            task = self.dm.get_task(task_id)
            if not task:
                continue
            scores = {m: self.dm.get_score(task_id, m) for m in BACKEND_MODELS}
            if len(set(scores.values())) <= 1:
                continue  # All models score the same, not a useful example

            dim = task.get("dimension", "unknown")
            if dim not in self._examples_by_dim:
                self._examples_by_dim[dim] = []
            self._examples_by_dim[dim].append({
                "task": task,
                "best_model": self.dm.get_oracle_model(task_id),
                "scores": scores,
            })

    def _select_examples(self, task: dict) -> list[dict]:
        """Select examples, prioritizing same-dimension tasks."""
        dim = task.get("dimension", "unknown")
        pool = self._examples_by_dim.get(dim, [])

        if len(pool) >= self.n_shots:
            return self._rng.sample(pool, self.n_shots)

        # If not enough same-dimension examples, add from other dimensions
        result = list(pool)
        other = []
        for d, exs in self._examples_by_dim.items():
            if d != dim:
                other.extend(exs)
        remaining = self.n_shots - len(result)
        if other and remaining > 0:
            result.extend(self._rng.sample(other, min(remaining, len(other))))
        return result

    async def route(self, task: dict) -> RoutingDecision:
        sanitized = self._sanitize_task(task)
        examples = self._select_examples(sanitized)
        prompt = build_few_shot_prompt(sanitized, examples, self.n_shots)

        start = time.monotonic()
        response = await self.client.complete(
            self.router_model, prompt, system_prompt=ROUTER_SYSTEM_PROMPT
        )
        latency = int((time.monotonic() - start) * 1000)

        if response.error:
            return RoutingDecision(
                task_id=task["task_id"],
                chosen_model=BACKEND_MODELS[0],
                confidence=0.0,
                router_input_tokens=response.input_tokens,
                router_output_tokens=response.output_tokens,
                router_latency_ms=latency,
                reasoning=f"Error: {response.error}, falling back to {BACKEND_MODELS[0]}",
            )

        chosen, reasoning = _parse_response(response.text)
        return RoutingDecision(
            task_id=task["task_id"],
            chosen_model=chosen,
            confidence=1.0,
            router_input_tokens=response.input_tokens,
            router_output_tokens=response.output_tokens,
            router_latency_ms=latency,
            reasoning=reasoning,
        )


def _parse_response(text: str) -> tuple[str, str]:
    """Parse LLM response to extract model choice.

    Strategy:
    1. Try JSON parsing
    2. Try regex for JSON-like pattern
    3. Search for model names in text
    4. Fallback to default
    """
    # Strategy 1: Direct JSON parse
    try:
        data = json.loads(text.strip())
        model = data.get("model", "")
        reasoning = data.get("reasoning", "")
        if model in BACKEND_MODELS:
            return model, reasoning
    except (json.JSONDecodeError, AttributeError):
        pass

    # Strategy 2: Extract JSON from markdown code blocks or embedded JSON
    json_patterns = [
        r'```(?:json)?\s*(\{.*?\})\s*```',
        r'(\{[^{}]*"model"[^{}]*\})',
    ]
    for pattern in json_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                model = data.get("model", "")
                reasoning = data.get("reasoning", "")
                if model in BACKEND_MODELS:
                    return model, reasoning
            except (json.JSONDecodeError, AttributeError):
                continue

    # Strategy 3: Search for model names in text
    for model in BACKEND_MODELS:
        if model in text:
            return model, f"Extracted from text: {text[:200]}"

    # Strategy 4: Fallback
    return BACKEND_MODELS[0], f"Parse failed, fallback. Raw: {text[:200]}"
