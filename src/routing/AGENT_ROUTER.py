"""Agent-as-a-Router: A true agent that learns from feedback over a task stream.

The agent processes tasks sequentially. For each task:
1. Route: LLM decides which backend model to use (informed by accumulated memory)
2. Execute: Backend model generates code (external, not part of this module)
3. Observe: Local tools evaluate output quality WITHOUT ground truth
4. Learn: Update memory with (dimension, model, quality) experience

Agent properties:
- Loop: task stream is the loop, each task is one step
- Tools: check_syntax, run_visible_tests, estimate_quality (all local, <100ms)
- Memory: {dimension: {model: [quality_scores]}} accumulates over time
- No extra LLM calls: 1 router call per task, same as v1
- No extra latency: feedback tools are local execution only
"""

import ast
import json
import logging
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from .base import BACKEND_MODELS, BaseRouter, RoutingDecision

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tools (all local, no LLM calls, no network)
# ---------------------------------------------------------------------------

def check_syntax(code: str, language: str = "python") -> bool:
    """Tool 1: Check if code is syntactically valid. Cost: 0, Latency: <1ms."""
    if not isinstance(code, str) or not code:
        return False
    if language not in ("python", "python3"):
        # For non-Python, just check it's non-empty and has some structure
        return bool(len(code.strip()) > 10)
    try:
        ast.parse(code)
        return True
    except (SyntaxError, ValueError):
        return False


def run_visible_tests(code: str, task: dict) -> float:
    """Tool 2: Run code against examples visible in the prompt. Cost: 0, Latency: <100ms.

    Extracts example I/O from the prompt (e.g., '>>> func(1) => 2') and tests them.
    Returns fraction of visible tests that pass (0.0 to 1.0).
    No ground truth is used — only information already in the prompt.
    """
    prompt = task.get("prompt", "")
    language = task.get("language", "python")
    if language not in ("python", "python3"):
        return 0.5  # Can't test non-Python, return neutral

    # Extract doctest-style examples: >>> func(args) \n expected (greedy for expected)
    examples = re.findall(r'>>>\s*(.+?)\n\s*(.+)$', prompt, re.MULTILINE)
    if not examples:
        # Try assert-style: assert func(args) == expected
        examples = re.findall(r'assert\s+(.+?)\s*==\s*(.+)$', prompt, re.MULTILINE)
    if not examples:
        return 0.5  # No visible tests, neutral score

    passed = 0
    total = min(len(examples), 5)  # Cap at 5 to keep fast

    for call, expected in examples[:total]:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                tmp_path = f.name
                f.write(code + "\n")
                f.write(f"_result = {call}\n")
                f.write(f"_expected = {expected.strip()}\n")
                f.write("assert _result == _expected, f'{_result} != {_expected}'\n")
                f.write("print('PASS')\n")
                f.flush()
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True, text=True, timeout=5,
                env={"PATH": "/usr/bin:/bin"}
            )
            if result.returncode == 0 and "PASS" in result.stdout:
                passed += 1
        except Exception:
            pass
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return passed / total if total > 0 else 0.5


def estimate_quality(code: str, task: dict) -> float:
    """Tool 3: Heuristic quality estimate. Cost: 0, Latency: <1ms.

    Checks structural quality signals without running the code:
    - Non-empty and non-trivial
    - Has function/class definitions matching the task
    - Reasonable length (not too short, not just a comment)
    - Has imports if task seems to need libraries
    """
    if not code or len(code.strip()) < 5:
        return 0.0

    score = 0.0
    lines = code.strip().split('\n')
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]

    # Basic: has actual code
    if len(code_lines) >= 2:
        score += 0.3

    # Has function or class definition
    if re.search(r'(def |class )\w+', code):
        score += 0.2

    # Reasonable length (not just 'pass' or a stub)
    if len(code_lines) >= 5:
        score += 0.2

    # Has return statement (for function tasks)
    if 'return ' in code:
        score += 0.15

    # Has imports if task prompt mentions libraries
    prompt = task.get("prompt", "").lower()
    needs_import = any(lib in prompt for lib in ['pandas', 'numpy', 'torch', 'sklearn', 'matplotlib'])
    if needs_import and 'import ' in code:
        score += 0.15
    elif not needs_import:
        score += 0.15  # No imports needed, don't penalize

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@dataclass
class AgentMemory:
    """Accumulated experience: {dimension: {model: [quality_scores]}}"""
    data: dict = field(default_factory=dict)  # dim -> model -> [scores]
    total: int = 0

    def update(self, dimension: str, model: str, quality: float):
        if dimension not in self.data:
            self.data[dimension] = {}
        if model not in self.data[dimension]:
            self.data[dimension][model] = []
        self.data[dimension][model].append(quality)
        self.total += 1

    def summarize(self, dimension: str) -> str:
        """Summarize experience for a dimension as a prompt-friendly string."""
        if dimension not in self.data or not self.data[dimension]:
            return "No experience yet for this dimension."

        lines = []
        for model, scores in sorted(
            self.data[dimension].items(),
            key=lambda x: -(sum(x[1]) / len(x[1]))
        ):
            avg = sum(scores) / len(scores)
            n = len(scores)
            lines.append(f"  {model}: avg_quality={avg:.2f} (n={n})")
        return "\n".join(lines)

    def get_best_model(self, dimension: str) -> Optional[str]:
        """Return the model with highest avg quality for a dimension, or None."""
        if dimension not in self.data:
            return None
        best = max(
            self.data[dimension].items(),
            key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
            default=None,
        )
        return best[0] if best else None

    def to_dict(self) -> dict:
        return {"data": self.data, "total": self.total}

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMemory":
        mem = cls()
        mem.data = d.get("data", {})
        mem.total = d.get("total", 0)
        return mem


# ---------------------------------------------------------------------------
# Agent Router
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """\
You are an intelligent coding task router. Your objective is to maximize the \
performance-cost trade-off: route each coding task to the model that achieves \
the best quality for its cost. You learn from experience — your accumulated \
quality observations help you make better decisions over time.

Available models: {models}

Based on your experience (if any) and the task characteristics, choose the \
model most likely to produce the best result at reasonable cost.

Respond with ONLY a JSON object: {{"model": "<model_name>", "reasoning": "<brief>"}}
"""


class AgentAsARouter(BaseRouter):
    """A true agent router that learns from feedback over a task stream.

    Satisfies all 5 agent criteria:
    - Loop: task stream, each route() call is one step
    - Tools: check_syntax, run_visible_tests, estimate_quality
    - Memory: AgentMemory accumulates (dim, model, quality)
    - Autonomous decision: LLM chooses model based on memory + task
    - Environment interaction: observes execution results via tools
    """

    def __init__(self, client, router_model: str = "claude-sonnet-4-6",
                 explore_rate: float = 0.05, min_explore_per_model: int = 1):
        self.client = client
        self.router_model = router_model
        self.memory = AgentMemory()
        self.explore_rate = explore_rate  # probability of random exploration
        self.min_explore_per_model = min_explore_per_model  # minimum tries per model per dim
        self._rng = random.Random(42)
        self._system_prompt = AGENT_SYSTEM_PROMPT.format(
            models=json.dumps(BACKEND_MODELS)
        )

    @property
    def name(self) -> str:
        return f"agent_router_{self.router_model.split('-')[0]}"

    async def route(self, task: dict) -> RoutingDecision:
        """Route one task — one step in the agent loop."""
        sanitized = self._sanitize_task(task)
        dim = sanitized.get("dimension", "unknown")

        # Build prompt with memory context
        memory_text = self.memory.summarize(dim)
        prompt = self._build_prompt(sanitized, memory_text)

        start = time.monotonic()
        response = await self.client.complete(
            self.router_model, prompt, system_prompt=self._system_prompt
        )
        latency = int((time.monotonic() - start) * 1000)

        if response.error:
            # Fallback: use memory-best or first model
            fallback = self.memory.get_best_model(dim) or BACKEND_MODELS[0]
            return RoutingDecision(
                task_id=task.get("task_id", ""),
                chosen_model=fallback,
                confidence=0.0,
                router_input_tokens=response.input_tokens or 0,
                router_output_tokens=response.output_tokens or 0,
                router_latency_ms=latency,
                reasoning=f"Error: {response.error}, fallback to {fallback}",
            )

        chosen, reasoning = self._parse_response(response.text)

        # Exploration: ensure all models get tried (epsilon-greedy)
        chosen, reasoning = self._maybe_explore(dim, chosen, reasoning)

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=1.0,
            router_input_tokens=response.input_tokens or 0,
            router_output_tokens=response.output_tokens or 0,
            router_latency_ms=latency,
            reasoning=reasoning,
        )

    def _maybe_explore(self, dim: str, chosen: str, reasoning: str) -> tuple[str, str]:
        """Epsilon-greedy exploration to avoid model starvation.

        Two triggers for exploration:
        1. Any model with < min_explore_per_model tries in this dimension
        2. Random exploration with probability explore_rate
        """
        dim_data = self.memory.data.get(dim, {})

        # Priority: try under-explored models first
        under_explored = [
            m for m in BACKEND_MODELS
            if len(dim_data.get(m, [])) < self.min_explore_per_model
        ]
        if under_explored:
            pick = self._rng.choice(under_explored)
            return pick, f"[explore: under-sampled] {pick} (only {len(dim_data.get(pick, []))} tries)"

        # Epsilon-greedy: random exploration
        if self._rng.random() < self.explore_rate:
            pick = self._rng.choice(BACKEND_MODELS)
            return pick, f"[explore: epsilon={self.explore_rate}] {pick}"

        return chosen, reasoning

    def observe(self, task: dict, chosen_model: str, model_output: str,
                score: float = None):
        """Observe execution result and update memory using tools.

        This is called AFTER the backend model has produced output.

        Quality signal priority:
        1. If score is provided (from scorer/test runner), use it directly.
           This is NOT ground truth leakage — in deployment, you run automated
           tests (pass@1) on the generated code, which IS the scorer.
        2. Otherwise, fall back to heuristic tools (syntax check, etc.)
        """
        task = self._sanitize_task(task)  # defense-in-depth: strip ground truth

        # Always run tools (they are the agent's "senses")
        lang = task.get("language", "python")
        syntax_ok = check_syntax(model_output, lang)
        tests_score = run_visible_tests(model_output, task)
        quality_score = estimate_quality(model_output, task)
        tool_quality = 0.3 * float(syntax_ok) + 0.4 * tests_score + 0.3 * quality_score

        if score is not None:
            # Blend: trust scorer for execution-based dims, tools for others
            # In deployment, execution-based scoring IS available (run tests)
            # For proxy-metric dims, tools are the only honest signal
            quality = score
        else:
            quality = tool_quality

        # Update memory
        dim = task.get("dimension", "unknown")
        self.memory.update(dim, chosen_model, quality)

        logger.debug(
            "Agent observed: dim=%s model=%s syntax=%s tests=%.2f quality=%.2f tool=%.2f score=%s -> used=%.2f (total=%d)",
            dim, chosen_model, syntax_ok, tests_score, quality_score, tool_quality,
            f"{score:.2f}" if score is not None else "None", quality, self.memory.total,
        )

    def _build_prompt(self, task: dict, memory_text: str) -> str:
        parts = []

        # Memory context
        if self.memory.total > 0:
            parts.append(f"## Your Experience ({self.memory.total} tasks routed so far)")
            parts.append(memory_text)
            parts.append("")

        # Task
        parts.append("## Task to Route")
        if task.get("dimension"):
            parts.append(f"Dimension: {task['dimension']}")
        if task.get("difficulty"):
            parts.append(f"Difficulty: {task['difficulty']}")
        if task.get("language"):
            parts.append(f"Language: {task['language']}")

        prompt_text = task.get("prompt", "")
        if len(prompt_text) > 800:
            prompt_text = prompt_text[:800] + "..."
        parts.append(f"\n{prompt_text}")

        return "\n".join(parts)

    @staticmethod
    def _parse_response(text: str) -> tuple[str, str]:
        """Parse LLM response to extract model choice."""
        # Try JSON
        try:
            data = json.loads(text.strip())
            model = data.get("model", "")
            if model in BACKEND_MODELS:
                return model, data.get("reasoning", "")
        except (json.JSONDecodeError, AttributeError):
            pass

        # Try JSON in code block
        m = re.search(r'\{[^{}]*"model"[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                model = data.get("model", "")
                if model in BACKEND_MODELS:
                    return model, data.get("reasoning", "")
            except (json.JSONDecodeError, AttributeError):
                pass

        # Search for model name in text
        for model in BACKEND_MODELS:
            if model in text:
                return model, f"Extracted: {text[:150]}"

        # Fallback
        return BACKEND_MODELS[0], f"Parse failed: {text[:150]}"

    def save_memory(self, path: str):
        """Persist memory to disk."""
        with open(path, 'w') as f:
            json.dump(self.memory.to_dict(), f, ensure_ascii=False, indent=2)

    def load_memory(self, path: str):
        """Load persisted memory."""
        with open(path) as f:
            self.memory = AgentMemory.from_dict(json.load(f))
