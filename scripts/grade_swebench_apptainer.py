#!/usr/bin/env python3
"""Grade SWE-bench Verified predictions with Apptainer.

This is the live sandbox verifier used by `run_ood_sandbox.py --verifier
sandbox-command`.  For each candidate patch it starts the cached SWE-bench SIF,
applies the patch inside `/testbed`, runs the SWE-bench eval script, and parses
the test log with the official SWE-bench grader.

Requirements:
  * apptainer on PATH
  * pandas + pyarrow
  * swebench importable in Python
  * SWE-bench Verified parquet dataset
  * cached instance SIF images
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import time
import traceback


def instance_to_sif(instance_id: str, sif_cache: str) -> str:
    id_docker = instance_id.replace("__", "_1776_")
    image = f"swebench/sweb.eval.x86_64.{id_docker}:latest".lower()
    sanitized = image.replace("/", "_").replace(":", "_")
    return os.path.join(sif_cache, f"{sanitized}.sif")


def run_apptainer(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["apptainer", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        text=True,
    )


def grade_one(
    instance: dict,
    model_patch: str,
    model_name: str,
    sif_cache: str,
    log_dir: str,
    eval_timeout: int,
) -> dict:
    instance_id = instance["instance_id"]
    result = {
        "instance_id": instance_id,
        "resolved": None,
        "apply_ok": False,
        "error": None,
        "log_path": None,
        "elapsed_s": 0.0,
    }
    t0 = time.time()

    from swebench.harness.constants import APPLY_PATCH_FAIL, KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION
    from swebench.harness.grading import get_eval_report
    from swebench.harness.test_spec.test_spec import make_test_spec

    sif = instance_to_sif(instance_id, sif_cache)
    if not os.path.exists(sif):
        result["error"] = f"SIF not found: {sif}"
        return result

    try:
        test_spec = make_test_spec(instance)
    except Exception as exc:
        result["error"] = f"make_test_spec: {exc}"
        return result

    instance_dir = Path(log_dir) / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    test_log = instance_dir / "test_output.txt"
    patch_path = instance_dir / "patch.diff"
    eval_path = instance_dir / "eval.sh"
    patch_path.write_text(model_patch)
    eval_path.write_text(test_spec.eval_script)

    name_base = instance_id.replace("_", "-").replace("/", "-")
    instance_name = f"grade-{name_base}"[:60] + f"-{os.getpid()}"
    try:
        start = run_apptainer(
            [
                "instance",
                "start",
                "--containall",
                "--writable-tmpfs",
                "--bind",
                f"{patch_path}:/tmp/patch.diff:ro",
                "--bind",
                f"{eval_path}:/tmp/eval.sh:ro",
                sif,
                instance_name,
            ],
            timeout=300,
        )
        if start.returncode != 0:
            result["error"] = f"instance start failed: {start.stderr.strip()[:300]}"
            return result

        apply = run_apptainer(
            [
                "exec",
                f"instance://{instance_name}",
                "bash",
                "-c",
                "cd /testbed && (git apply --verbose /tmp/patch.diff 2>&1 || "
                "git apply -3 --verbose /tmp/patch.diff 2>&1 || "
                "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff 2>&1)",
            ],
            timeout=120,
        )
        result["apply_ok"] = apply.returncode == 0
        if not result["apply_ok"]:
            (instance_dir / "apply.log").write_text(apply.stdout + "\n---STDERR---\n" + apply.stderr)
            result["error"] = "patch apply failed"
            test_log.write_text(APPLY_PATCH_FAIL + "\n")
        else:
            (instance_dir / "apply.log").write_text(apply.stdout + "\n---STDERR---\n" + apply.stderr)
            with test_log.open("w") as f:
                subprocess.run(
                    ["apptainer", "exec", f"instance://{instance_name}", "bash", "/tmp/eval.sh"],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=eval_timeout,
                )

        result["log_path"] = str(test_log)
        try:
            report = get_eval_report(
                test_spec=test_spec,
                prediction={
                    KEY_INSTANCE_ID: instance_id,
                    KEY_MODEL: model_name,
                    KEY_PREDICTION: model_patch,
                },
                test_log_path=str(test_log),
                include_tests_status=True,
            )
            result["report"] = report.get(instance_id, report)
            result["resolved"] = bool(result["report"].get("resolved", False))
        except Exception as exc:
            result["error"] = f"grade parse: {exc}"

    except subprocess.TimeoutExpired:
        result["error"] = f"timeout after {eval_timeout}s"
    except Exception as exc:
        result["error"] = f"unexpected: {exc}"
        traceback.print_exc()
    finally:
        try:
            run_apptainer(["instance", "stop", instance_name], timeout=30)
        except Exception:
            pass
        result["elapsed_s"] = round(time.time() - t0, 1)

    return result


def worker(args: tuple[dict, str, str, str, str, int]) -> dict:
    return grade_one(*args)


def load_predictions(path: Path) -> dict[str, dict]:
    payload = json.load(path.open())
    if isinstance(payload, dict) and isinstance(payload.get("items"), dict):
        return payload["items"]
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"unsupported predictions file: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preds", required=True)
    parser.add_argument("--dataset_path", required=True)
    parser.add_argument("--sif_cache", required=True)
    parser.add_argument("--log_dir", required=True)
    parser.add_argument("--out", default=None, help="where to write report json; default: log_dir/report.json")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=500)
    parser.add_argument("--only", default=None, help="comma-separated instance ids to grade")
    parser.add_argument("--skip_done", action="store_true")
    parser.add_argument("--eval_timeout", type=int, default=1200)
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.out) if args.out else log_dir / "report.json"

    existing = {}
    if args.skip_done and report_path.exists():
        existing = json.load(report_path.open())

    import pandas as pd

    preds = load_predictions(Path(args.preds))
    rows = pd.read_parquet(args.dataset_path).iloc[args.start : args.end].to_dict("records")
    if args.only:
        wanted = set(args.only.split(","))
        rows = [row for row in rows if row["instance_id"] in wanted]

    work = []
    for row in rows:
        instance_id = row["instance_id"]
        pred = preds.get(instance_id)
        if not pred:
            continue
        patch = pred.get("model_patch", "").strip()
        if not patch:
            continue
        if instance_id in existing and existing[instance_id].get("resolved") is not None:
            continue
        model_name = pred.get("model_name_or_path") or "unknown"
        work.append((row, patch, model_name, args.sif_cache, str(log_dir), args.eval_timeout))

    print(f"to grade: {len(work)} instances (preds={len(preds)}, dataset_slice={len(rows)})")
    results = dict(existing)
    if work:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(worker, payload): payload[0]["instance_id"] for payload in work}
            for index, future in enumerate(as_completed(futures), start=1):
                instance_id = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    row = {"instance_id": instance_id, "resolved": None, "error": str(exc)}
                results[instance_id] = row
                status = "resolved" if row.get("resolved") else ("applied" if row.get("apply_ok") else "failed")
                print(
                    f"[{index}/{len(work)}] {status} {instance_id} "
                    f"err={row.get('error') or '-'} elapsed={row.get('elapsed_s', 0)}s",
                    flush=True,
                )
                tmp = report_path.with_suffix(report_path.suffix + ".tmp")
                tmp.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
                tmp.replace(report_path)

    resolved = sum(1 for item in results.values() if item.get("resolved"))
    apply_ok = sum(1 for item in results.values() if item.get("apply_ok"))
    print("\n=== SUMMARY ===")
    print(f"preds total: {len(preds)}")
    print(f"graded:      {len(results)}")
    print(f"apply_ok:    {apply_ok}")
    print(f"resolved:    {resolved}")
    print(f"report:      {report_path}")


if __name__ == "__main__":
    main()
