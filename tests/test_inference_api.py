from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.inference import ACRouter  # noqa: E402


class InferenceAPITest(unittest.TestCase):
    def test_run_with_verifier_escalates_and_updates_memory(self):
        router = ACRouter(
            candidate_models=["toy-fast", "toy-balanced", "toy-strong"],
            cheap_chain=["toy-fast", "toy-balanced"],
            escalate_to="toy-strong",
            k=1,
        )
        task = {"task_id": "t1", "dimension": "code_generation", "prompt": "write code"}

        def call_model(model, _task):
            return {"model": model, "score": {"toy-fast": 0.2, "toy-balanced": 0.6, "toy-strong": 1.0}[model]}

        def verify(response, _task, _model):
            score = response["score"]
            return {"resolved": score >= 1.0, "apply_ok": score >= 0.2, "score": score}

        decision = router.run_with_verifier(task, call_model=call_model, verify=verify)

        self.assertTrue(decision.escalated)
        self.assertEqual(decision.chosen_model, "toy-strong")
        self.assertEqual(decision.candidate_chain, ["toy-fast", "toy-balanced", "toy-strong"])
        self.assertEqual(router.route(task).chosen_model, "toy-strong")

    def test_route_can_use_dimension_map_without_execution(self):
        router = ACRouter(
            candidate_models=["toy-fast", "toy-balanced", "toy-strong"],
            cheap_chain=["toy-fast"],
            escalate_to="toy-strong",
            dimension_map={"bug_fixing": "toy-balanced"},
        )
        decision = router.route({"task_id": "t2", "dimension": "bug_fixing"})
        self.assertEqual(decision.chosen_model, "toy-balanced")
        self.assertEqual(decision.reason, "dimension_map")


if __name__ == "__main__":
    unittest.main()

