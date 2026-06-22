#!/usr/bin/env python3
"""Minimal example: call ACRouter inside an arbitrary inference workflow."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from acrouter_repro.inference import ACRouter  # noqa: E402


def call_model(model: str, task: dict) -> dict:
    """Replace this function with your provider/client call."""

    outputs = {
        "toy-fast": {"patch": "fast attempt", "quality": 0.2},
        "toy-balanced": {"patch": "balanced attempt", "quality": 0.6},
        "toy-strong": {"patch": "strong attempt", "quality": 1.0},
    }
    return {"model": model, **outputs[model]}


def verify(response: dict, task: dict, model: str) -> dict:
    """Replace this function with tests, sandbox grading, or workflow checks."""

    quality = float(response["quality"])
    return {
        "resolved": quality >= 1.0,
        "apply_ok": quality >= 0.2,
        "score": quality,
    }


def main() -> None:
    router = ACRouter(
        candidate_models=["toy-fast", "toy-balanced", "toy-strong"],
        cheap_chain=["toy-fast", "toy-balanced"],
        escalate_to="toy-strong",
        k=1,
    )
    task = {
        "task_id": "demo_task_001",
        "dimension": "code_generation",
        "prompt": "Implement a robust parser for key=value lines.",
    }

    decision = router.run_with_verifier(task, call_model=call_model, verify=verify)
    print(decision.to_dict())
    print("final_response=", decision.final_response)


if __name__ == "__main__":
    main()

