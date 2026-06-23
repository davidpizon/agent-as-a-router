from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_python(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


class DemoTests(unittest.TestCase):
    def test_api_coding_solver_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_python(
                "demos/api_coding_solver/solve.py",
                "--config",
                "demos/api_coding_solver/models.example.json",
                "--problem-file",
                "demos/api_coding_solver/problems/two_sum.txt",
                "--output-dir",
                tmp,
                "--max-models",
                "2",
                "--dry-run",
            )
            run_dirs = sorted(Path(tmp).iterdir())
            self.assertEqual(len(run_dirs), 1)
            plan = json.loads((run_dirs[0] / "request_plan.json").read_text())
            summary = json.loads((run_dirs[0] / "summary.json").read_text())

            self.assertTrue(plan["dry_run"])
            self.assertEqual(plan["candidate_count"], 2)
            self.assertEqual(plan["candidates"][0]["api_name"], "openrouter")
            self.assertEqual(summary["status"], "dry_run")
            self.assertNotIn("sk-", (run_dirs[0] / "request_plan.json").read_text())

    def test_commercial_cli_router_dry_run_routes_to_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_python(
                "demos/commercial_cli_router/router_mvp.py",
                "--config",
                "demos/commercial_cli_router/tools.example.json",
                "--prompt",
                "Patch this repository so pytest passes",
                "--output-dir",
                tmp,
                "--dry-run",
            )
            run_dir = next(Path(tmp).iterdir())
            route = json.loads((run_dir / "route.json").read_text())

            self.assertTrue(route["dry_run"])
            self.assertEqual(route["selected_tool"], "codex")
            self.assertEqual(route["command"][0], "codex")
            self.assertIn("Patch this repository", route["command"][-1])

    def test_commercial_cli_router_npm_wrapper_is_private(self) -> None:
        package_path = ROOT / "demos/commercial_cli_router/npm/package.json"
        package = json.loads(package_path.read_text())
        self.assertTrue(package["private"])
        self.assertEqual(package["bin"]["acrouter-cli-router"], "bin/acrouter-cli-router.js")
        self.assertTrue((package_path.parent / "bin/acrouter-cli-router.js").exists())


if __name__ == "__main__":
    unittest.main()
