from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.id_repro import run_id  # noqa: E402
from acrouter_repro.ood_sandbox import run_ood_sandbox  # noqa: E402
from acrouter_repro.ood_repro import OODData, score_ood  # noqa: E402
from acrouter_repro.predictions import patch_sha256  # noqa: E402
from acrouter_repro.sandbox_verifier import ReportCacheVerifier  # noqa: E402
from acrouter_repro.sandbox_verifier import PatchCandidate, SandboxCommandVerifier  # noqa: E402


class SandboxVerifierTests(unittest.TestCase):
    def test_id_default_is_clean_val_to_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "id"
            (data / "splits").mkdir(parents=True)
            (data / "voter_decisions").mkdir()
            (data / "splits" / "train.json").write_text("[]")
            (data / "splits" / "val.json").write_text(json.dumps(["task-val"]))
            (data / "splits" / "test.json").write_text(json.dumps(["task-test"]))
            rows = [
                {"task_id": "task-val", "dimension": "math"},
                {"task_id": "task-test", "dimension": "math"},
            ]
            (data / "task_dimensions.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            labels = [
                {
                    "task_id": "task-val",
                    "all_scores": {"MiniMax-M2.7": 1, "gpt-5.4": 0},
                },
                {
                    "task_id": "task-test",
                    "all_scores": {"MiniMax-M2.7": 1, "gpt-5.4": 0},
                },
            ]
            (data / "oracle_labels.jsonl").write_text("\n".join(json.dumps(row) for row in labels) + "\n")
            token_rows = [
                {"task_id": "task-val", "model": "MiniMax-M2.7", "input_tokens": 1, "output_tokens": 1},
                {"task_id": "task-test", "model": "MiniMax-M2.7", "input_tokens": 1, "output_tokens": 1},
            ]
            (data / "tokens.jsonl").write_text("\n".join(json.dumps(row) for row in token_rows) + "\n")
            decisions = [
                {"task_id": "task-val", "chosen_model": "MiniMax-M2.7"},
                {"task_id": "task-test", "chosen_model": "MiniMax-M2.7"},
            ]
            (data / "voter_decisions" / "dimension_best.jsonl").write_text(
                "\n".join(json.dumps(row) for row in decisions) + "\n"
            )

            clean = run_id(data, root / "out-clean")
            self.assertEqual(clean["metrics"]["policy"], "hierarchical")
            self.assertEqual(clean["metrics"]["tune_split"], "train+val")
            self.assertEqual(clean["metrics"]["eval_split"], "test")
            self.assertEqual(clean["metrics"]["leakage_risk"], "none")

            leaky = run_id(data, root / "out-leaky", tune_split="test", eval_split="test", policy="voter")
            self.assertEqual(leaky["metrics"]["leakage_risk"], "test_tuned_not_clean")

    def test_report_cache_checks_patch_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()
            good_patch = "diff --git a/a.py b/a.py\n"
            payload = {
                "schema_version": 1,
                "model": "MiniMax-M2.7",
                "items": {
                    "repo__issue-1": {
                        "patch_sha256": patch_sha256(good_patch),
                        "resolved": True,
                        "apply_ok": True,
                    }
                },
            }
            (cache / "MiniMax-M2.7.json").write_text(json.dumps(payload))
            verifier = ReportCacheVerifier(cache)

            ok = verifier.verify(PatchCandidate("repo__issue-1", "MiniMax-M2.7", good_patch))
            self.assertTrue(ok.resolved)
            bad = verifier.verify(PatchCandidate("repo__issue-1", "MiniMax-M2.7", good_patch + "\n# changed"))
            self.assertFalse(bad.resolved)
            self.assertIn("patch_hash_mismatch", bad.error or "")

    def test_ood_sandbox_uses_verifier_result_not_matrix_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = "MiniMax-M2.7"
            matrix = {
                "ids": ["repo__issue-1"],
                "models": [model, "kimi-k2.5", "gpt-5.4", "glm-5", "claude-opus-4-6"],
                "matrix": {
                    "repo__issue-1": {
                        model: {"resolved": False, "apply_ok": False, "cost_usd": 0.1},
                        "kimi-k2.5": {"resolved": False, "apply_ok": False, "cost_usd": 0.1},
                        "gpt-5.4": {"resolved": False, "apply_ok": False, "cost_usd": 0.1},
                        "glm-5": {"resolved": False, "apply_ok": False, "cost_usd": 0.1},
                        "claude-opus-4-6": {"resolved": False, "apply_ok": False, "cost_usd": 0.1},
                    }
                },
            }
            matrix_path = root / "matrix.json"
            matrix_path.write_text(json.dumps(matrix))

            patch = "diff --git a/a.py b/a.py\n"
            preds = root / "predictions"
            preds.mkdir()
            pred_payload = {
                "schema_version": 1,
                "model": model,
                "items": {
                    "repo__issue-1": {
                        "instance_id": "repo__issue-1",
                        "model_patch": patch,
                    }
                },
            }
            (preds / "MiniMax-M2.7.json").write_text(json.dumps(pred_payload))

            cache = root / "cache"
            cache.mkdir()
            cache_payload = {
                "schema_version": 1,
                "model": model,
                "items": {
                    "repo__issue-1": {
                        "patch_sha256": patch_sha256(patch),
                        "resolved": True,
                        "apply_ok": True,
                    }
                },
            }
            (cache / "MiniMax-M2.7.json").write_text(json.dumps(cache_payload))

            result = run_ood_sandbox(matrix_path, preds, root / "out", ReportCacheVerifier(cache))
            self.assertEqual(result["metrics"]["AvgPerf%"], 100.0)
            self.assertTrue(result["decisions"][0]["resolved"])

    def test_sandbox_command_verifier_parses_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "fake_grade.py"
            fake.write_text(
                "\n".join(
                    [
                        "import argparse, json",
                        "p=argparse.ArgumentParser()",
                        "p.add_argument('--preds')",
                        "p.add_argument('--out')",
                        "p.add_argument('--log_dir')",
                        "p.add_argument('--dataset_path')",
                        "p.add_argument('--workers')",
                        "p.add_argument('--only')",
                        "p.add_argument('--eval_timeout')",
                        "a=p.parse_args()",
                        "preds=json.load(open(a.preds))",
                        "tid=next(iter(preds))",
                        "json.dump({tid:{'instance_id':tid,'resolved':True,'apply_ok':True,'report':{'resolved':True,'patch_successfully_applied':True}}}, open(a.out,'w'))",
                    ]
                )
            )
            verifier = SandboxCommandVerifier(
                work_root=root / "work",
                grade_script=fake,
                dataset_path=root / "dataset.parquet",
                python_executable=sys.executable,
            )
            result = verifier.verify(PatchCandidate("repo__issue-1", "MiniMax-M2.7", "diff --git a/a b/a\n"))
            self.assertTrue(result.resolved)
            self.assertFalse(result.from_cache)
            cached = verifier.verify(PatchCandidate("repo__issue-1", "MiniMax-M2.7", "diff --git a/a b/a\n"))
            self.assertTrue(cached.from_cache)

    def test_score_uses_explicit_false_result_without_matrix_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = {
                "ids": ["repo__issue-1"],
                "models": ["MiniMax-M2.7"],
                "matrix": {
                    "repo__issue-1": {
                        "MiniMax-M2.7": {"resolved": True, "apply_ok": True, "cost_usd": 0.1}
                    }
                },
            }
            matrix_path = root / "matrix.json"
            matrix_path.write_text(json.dumps(matrix))
            data = OODData(matrix_path)
            rows = [
                {
                    "task_id": "repo__issue-1",
                    "chosen_model": "MiniMax-M2.7",
                    "resolved": False,
                    "apply_ok": False,
                    "cost_usd": 0.1,
                    "n_steps": 1,
                    "chain_run": ["MiniMax-M2.7"],
                }
            ]
            metrics = score_ood(data, rows)
            self.assertEqual(metrics["AvgPerf%"], 0.0)
            self.assertEqual(metrics["Apply_ok%"], 0.0)


if __name__ == "__main__":
    unittest.main()
