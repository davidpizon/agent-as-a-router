"""Prompt templates for LLM-based routing."""

ROUTER_SYSTEM_PROMPT = """\
You are a coding task router. Your objective is to maximize the performance-cost \
trade-off: choose the model that achieves the best quality for its cost on this task.

## Available Models (sorted by cost, high to low)

1. **claude-opus-4-6**: Premium. Excels at code completion, bug fixing, code generation, \
and multi-language tasks. Strong on complex tasks requiring deep reasoning.

2. **claude-sonnet-4-6**: High. Good at code completion, bug fixing, and multi-language tasks. \
Good balance of speed and quality.

3. **gpt-5.4**: High. Strong at code refactoring and test generation. \
Good overall capabilities with competitive performance.

4. **glm-5**: Mid. Strong at algorithm design and bug fixing. \
Good cost-performance balance for algorithmic and code generation tasks.

5. **MiniMax-M2.7**: Mid. Strong at code refactoring and code completion. \
Cost-efficient option with good overall balance.

6. **kimi-k2.5**: Low. Competitive on data science and code understanding tasks. \
Very cost-efficient. Good for straightforward tasks.

7. **qwen3.5-plus**: Low. Exceptional at algorithm and competitive programming tasks. \
Also good at code completion. Best choice for algorithmic challenges.

8. **Qwen3-Max**: Low. Strong at test generation and algorithm tasks. \
Best quality-cost ratio for test generation scenarios.

## Instructions

Analyze the task and choose the model that maximizes quality relative to cost.
Consider the task's dimension, difficulty, language, and complexity.
Prefer cheaper models when quality is comparable.

Respond with ONLY a JSON object:
{"model": "<model_name>", "reasoning": "<brief explanation>"}
"""


def build_zero_shot_prompt(task: dict) -> str:
    """Build a zero-shot routing prompt from a sanitized task."""
    parts = [f"## Task to Route\n"]

    if task.get("dimension"):
        parts.append(f"**Dimension**: {task['dimension']}")
    if task.get("difficulty"):
        parts.append(f"**Difficulty**: {task['difficulty']}")
    if task.get("language"):
        parts.append(f"**Language**: {task['language']}")
    if task.get("eval_method"):
        parts.append(f"**Evaluation**: {task['eval_method']}")

    parts.append(f"\n**Prompt**:\n{task.get('prompt', '')}")

    return "\n".join(parts)


def build_few_shot_prompt(task: dict, examples: list[dict], n_shots: int = 3) -> str:
    """Build a few-shot routing prompt with examples from training data.

    Each example in `examples` should have:
      - task: sanitized task dict
      - best_model: the oracle-chosen model
      - scores: dict of model -> score
    """
    parts = ["## Examples\n"]

    for i, ex in enumerate(examples[:n_shots], 1):
        ex_task = ex["task"]
        prompt_preview = ex_task.get("prompt", "")[:300]
        if len(ex_task.get("prompt", "")) > 300:
            prompt_preview += "..."

        parts.append(f"### Example {i}")
        parts.append(f"- Dimension: {ex_task.get('dimension', 'unknown')}")
        parts.append(f"- Difficulty: {ex_task.get('difficulty', 'unknown')}")
        parts.append(f"- Language: {ex_task.get('language', 'python')}")
        parts.append(f"- Prompt: {prompt_preview}")
        parts.append(f"- **Best model**: {ex['best_model']}")

        # Show score differences if available
        scores = ex.get("scores", {})
        if scores:
            score_str = ", ".join(f"{m}: {s:.2f}" for m, s in sorted(scores.items()) if s is not None)
            parts.append(f"- Scores: {score_str}")

        parts.append("")

    parts.append("---\n")
    parts.append("Now route the following task:\n")
    parts.append(build_zero_shot_prompt(task))

    return "\n".join(parts)
