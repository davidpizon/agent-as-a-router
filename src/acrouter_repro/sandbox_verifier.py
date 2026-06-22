"""Sandbox verification backends for OOD routing.

The router must not decide from a precomputed resolved label matrix.  It should
submit the candidate patch to a verifier and use only the verifier response.
This module provides two verifier implementations:

* ReportCacheVerifier reads hash-checked reports produced by a sandbox run.
* SandboxCommandVerifier writes a one-instance preds.json and invokes an
  external sandbox command, then caches the parsed result by patch hash.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Any

from .predictions import patch_sha256, safe_model_filename


SECRET_ENV_MARKERS = (
    "API_KEY",
    "ANTHROPIC",
    "OPENAI",
    "OPENROUTER",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
)


@dataclass(frozen=True)
class PatchCandidate:
    task_id: str
    model: str
    patch: str

    @property
    def patch_sha256(self) -> str:
        return patch_sha256(self.patch)


@dataclass
class VerificationResult:
    task_id: str
    model: str
    patch_sha256: str
    resolved: bool = False
    apply_ok: bool = False
    verifier: str = "unknown"
    from_cache: bool = False
    error: str | None = None
    log_path: str | None = None
    elapsed_s: float = 0.0
    tests: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def scrubbed_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(marker in upper for marker in SECRET_ENV_MARKERS):
            continue
        env[key] = value
    if extra_env:
        env.update(extra_env)
    return env


def _safe_task_fragment(task_id: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id).strip("._")
    return fragment[:120] or "task"


def summarize_tests(report_payload: dict[str, Any]) -> dict[str, Any]:
    report = report_payload.get("report")
    if not isinstance(report, dict):
        report = report_payload
    status = report.get("tests_status") if isinstance(report, dict) else None
    if not isinstance(status, dict):
        return {}
    out: dict[str, Any] = {}
    for bucket, values in status.items():
        if not isinstance(values, dict):
            continue
        success = values.get("success") or []
        failure = values.get("failure") or []
        out[bucket] = {
            "success": len(success) if isinstance(success, list) else 0,
            "failure": len(failure) if isinstance(failure, list) else 0,
        }
    return out


def extract_report_item(report_payload: Any, task_id: str) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None
    if task_id in report_payload and isinstance(report_payload[task_id], dict):
        return report_payload[task_id]
    items = report_payload.get("items")
    if isinstance(items, dict) and isinstance(items.get(task_id), dict):
        return items[task_id]
    reports = report_payload.get("reports")
    if isinstance(reports, dict) and isinstance(reports.get(task_id), dict):
        return reports[task_id]
    resolved_ids = report_payload.get("resolved")
    if isinstance(resolved_ids, list):
        return {
            "instance_id": task_id,
            "resolved": task_id in set(resolved_ids),
            "apply_ok": task_id not in set(report_payload.get("empty_generation", [])),
            "error": None,
        }
    return None


def result_from_report_item(
    item: dict[str, Any],
    candidate: PatchCandidate,
    verifier: str,
    from_cache: bool,
) -> VerificationResult:
    report = item.get("report") if isinstance(item.get("report"), dict) else item
    resolved = bool(item.get("resolved", report.get("resolved", False)))
    apply_ok = bool(
        item.get(
            "apply_ok",
            report.get("patch_successfully_applied", report.get("apply_ok", False)),
        )
    )
    tests = item.get("tests") if isinstance(item.get("tests"), dict) else summarize_tests(item)
    return VerificationResult(
        task_id=candidate.task_id,
        model=candidate.model,
        patch_sha256=candidate.patch_sha256,
        resolved=resolved,
        apply_ok=apply_ok,
        verifier=verifier,
        from_cache=from_cache,
        error=item.get("error"),
        log_path=item.get("log_path"),
        elapsed_s=float(item.get("elapsed_s", 0.0) or 0.0),
        tests=tests,
    )


class ReportCacheVerifier:
    """Read a sandbox report cache, checking the patch hash before use."""

    def __init__(self, cache_root: Path):
        self.cache_root = Path(cache_root)
        self._model_cache: dict[str, dict[str, dict]] = {}

    def _load_model(self, model: str) -> dict[str, dict]:
        if model in self._model_cache:
            return self._model_cache[model]
        path = self.cache_root / f"{safe_model_filename(model)}.json"
        with path.open() as f:
            payload = json.load(f)
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, dict):
            raise ValueError(f"cache file has no items object: {path}")
        self._model_cache[model] = items
        return items

    def verify(self, candidate: PatchCandidate) -> VerificationResult:
        try:
            item = self._load_model(candidate.model).get(candidate.task_id)
        except FileNotFoundError:
            item = None
        if not item:
            return VerificationResult(
                task_id=candidate.task_id,
                model=candidate.model,
                patch_sha256=candidate.patch_sha256,
                verifier="report-cache",
                from_cache=True,
                error="missing_cache_entry",
            )
        expected_hash = item.get("patch_sha256")
        if expected_hash and expected_hash != candidate.patch_sha256:
            return VerificationResult(
                task_id=candidate.task_id,
                model=candidate.model,
                patch_sha256=candidate.patch_sha256,
                verifier="report-cache",
                from_cache=True,
                error=f"patch_hash_mismatch:{expected_hash}",
            )
        return result_from_report_item(item, candidate, "report-cache", True)


class SandboxCommandVerifier:
    """Invoke an external sandbox verifier command for one patch at a time."""

    def __init__(
        self,
        work_root: Path,
        command_template: str | None = None,
        grade_script: Path | None = None,
        dataset_path: Path | None = None,
        sif_cache: Path | None = None,
        python_executable: str = sys.executable,
        eval_timeout: int = 1200,
        command_timeout: int = 1800,
        extra_env: dict[str, str] | None = None,
    ):
        self.work_root = Path(work_root)
        self.command_template = command_template
        self.grade_script = Path(grade_script) if grade_script else None
        self.dataset_path = Path(dataset_path) if dataset_path else None
        self.sif_cache = Path(sif_cache) if sif_cache else None
        self.python_executable = python_executable
        self.eval_timeout = eval_timeout
        self.command_timeout = command_timeout
        self.extra_env = extra_env or {}

    def _result_cache_path(self, candidate: PatchCandidate) -> Path:
        return (
            self.work_root
            / "result_cache"
            / safe_model_filename(candidate.model)
            / f"{_safe_task_fragment(candidate.task_id)}.{candidate.patch_sha256}.json"
        )

    def _build_command(self, candidate: PatchCandidate, run_dir: Path, preds: Path, report: Path) -> list[str]:
        format_values = {
            "task_id": candidate.task_id,
            "model": candidate.model,
            "patch_sha256": candidate.patch_sha256,
            "preds_path": str(preds),
            "report_path": str(report),
            "log_dir": str(run_dir / "logs"),
            "work_dir": str(run_dir),
            "dataset_path": str(self.dataset_path or ""),
            "sif_cache": str(self.sif_cache or ""),
            "eval_timeout": str(self.eval_timeout),
        }
        if self.command_template:
            return shlex.split(self.command_template.format(**format_values))
        if not self.grade_script or not self.dataset_path:
            raise ValueError("sandbox-command needs --grade-script and --dataset-path, or --command-template")
        cmd = [
            self.python_executable,
            str(self.grade_script),
            "--preds",
            str(preds),
            "--dataset_path",
            str(self.dataset_path),
            "--log_dir",
            str(run_dir / "logs"),
            "--out",
            str(report),
            "--workers",
            "1",
            "--only",
            candidate.task_id,
            "--eval_timeout",
            str(self.eval_timeout),
        ]
        if self.sif_cache:
            cmd.extend(["--sif_cache", str(self.sif_cache)])
        return cmd

    def verify(self, candidate: PatchCandidate) -> VerificationResult:
        cache_path = self._result_cache_path(candidate)
        if cache_path.exists():
            with cache_path.open() as f:
                cached = json.load(f)
            cached["from_cache"] = True
            return VerificationResult(**cached)

        t0 = time.time()
        run_dir = (
            self.work_root
            / "runs"
            / safe_model_filename(candidate.model)
            / f"{_safe_task_fragment(candidate.task_id)}.{candidate.patch_sha256[:12]}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        preds_path = run_dir / "preds.json"
        report_path = run_dir / "report.json"
        preds_payload = {
            candidate.task_id: {
                "instance_id": candidate.task_id,
                "model_name_or_path": candidate.model,
                "model_patch": candidate.patch,
            }
        }
        with preds_path.open("w") as f:
            json.dump(preds_payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

        cmd = self._build_command(candidate, run_dir, preds_path, report_path)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(run_dir),
                env=scrubbed_env(self.extra_env),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.command_timeout,
            )
            (run_dir / "stdout.txt").write_text(proc.stdout)
            (run_dir / "stderr.txt").write_text(proc.stderr)
        except subprocess.TimeoutExpired as exc:
            (run_dir / "stdout.txt").write_text(exc.stdout or "")
            (run_dir / "stderr.txt").write_text(exc.stderr or "")
            result = VerificationResult(
                task_id=candidate.task_id,
                model=candidate.model,
                patch_sha256=candidate.patch_sha256,
                verifier="sandbox-command",
                error=f"command_timeout:{self.command_timeout}",
                elapsed_s=round(time.time() - t0, 3),
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
                f.write("\n")
            return result

        if report_path.exists():
            with report_path.open() as f:
                report_payload = json.load(f)
            item = extract_report_item(report_payload, candidate.task_id)
            if item:
                result = result_from_report_item(item, candidate, "sandbox-command", False)
            else:
                result = VerificationResult(
                    task_id=candidate.task_id,
                    model=candidate.model,
                    patch_sha256=candidate.patch_sha256,
                    verifier="sandbox-command",
                    error="report_missing_task",
                )
        else:
            result = VerificationResult(
                task_id=candidate.task_id,
                model=candidate.model,
                patch_sha256=candidate.patch_sha256,
                verifier="sandbox-command",
                error=f"command_failed:{proc.returncode}",
            )
        result.elapsed_s = round(time.time() - t0, 3)
        if proc.returncode != 0 and not result.error:
            result.error = f"command_returncode:{proc.returncode}"

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        return result
