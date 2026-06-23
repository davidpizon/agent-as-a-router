#!/usr/bin/env python3
"""Route one coding problem across OpenAI-compatible chat APIs."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM_PROMPT = (
    "You are a senior competitive-programming and software-engineering "
    "assistant. Produce a correct, self-contained solution."
)

DEFAULT_USER_TEMPLATE = """Solve the programming task below.

Return a short explanation followed by one complete Python solution in a fenced
Python code block.

Task:
{problem}
"""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_problem(args: argparse.Namespace) -> str:
    if args.problem:
        return args.problem
    if args.problem_file:
        return Path(args.problem_file).read_text()
    raise SystemExit("Provide --problem or --problem-file.")


def model_slug(model: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_")
    return slug or "model"


def iter_candidates(config: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for api in config.get("apis", []):
        for entry in api.get("models", []):
            if isinstance(entry, str):
                model = {"name": entry}
            else:
                model = dict(entry)
            candidates.append(
                {
                    "api_name": api["name"],
                    "base_url": api["base_url"].rstrip("/"),
                    "api_key_env": api.get("api_key_env", ""),
                    "referer_env": api.get("referer_env", ""),
                    "title": api.get("title", "ACRouter API coding solver demo"),
                    "model": model["name"],
                    "temperature": model.get("temperature", config.get("temperature", 0.2)),
                    "max_tokens": model.get("max_tokens", config.get("max_tokens", 4096)),
                }
            )
    if not candidates:
        raise SystemExit("Config must contain at least one API model candidate.")
    return candidates


def build_messages(config: dict[str, Any], problem: str) -> list[dict[str, str]]:
    system_prompt = config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    template = config.get("user_template", DEFAULT_USER_TEMPLATE)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": template.format(problem=problem)},
    ]


def call_chat_completion(
    candidate: dict[str, Any],
    messages: list[dict[str, str]],
    timeout: int,
) -> dict[str, Any]:
    token_name = candidate["api_key_env"]
    token = os.environ.get(token_name, "")
    if not token:
        raise RuntimeError(f"Missing environment variable {token_name}")

    payload = {
        "model": candidate["model"],
        "messages": messages,
        "temperature": candidate["temperature"],
        "max_tokens": candidate["max_tokens"],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Title": candidate["title"],
    }
    referer_env = candidate.get("referer_env")
    if referer_env and os.environ.get(referer_env):
        headers["HTTP-Referer"] = os.environ[referer_env]

    request = urllib.request.Request(
        f"{candidate['base_url']}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{candidate['api_name']} HTTP {exc.code}: {detail}") from exc


def extract_message(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    return json.dumps(content, indent=2, ensure_ascii=False)


def extract_python_code(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if not blocks:
        return text.rstrip() + "\n"
    return max((block.strip() for block in blocks), key=len) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def new_run_dir(output_root: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"{int((time.time() % 1) * 1000):03d}"
    return output_root / f"{stamp}-{suffix}-{os.getpid()}"


def run_verifier(command: str, workspace: Path, timeout: int) -> dict[str, Any]:
    rendered = command.format(workspace=str(workspace), solution=str(workspace / "solution.py"))
    completed = subprocess.run(
        rendered,
        cwd=workspace,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "command": rendered,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
    }


def solve(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config = load_json(config_path)
    problem = read_problem(args)
    messages = build_messages(config, problem)
    candidates = iter_candidates(config)
    if args.max_models:
        candidates = candidates[: args.max_models]

    output_root = Path(args.output_dir)
    run_dir = new_run_dir(output_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(messages[-1]["content"])
    write_json(
        run_dir / "request_plan.json",
        {
            "config": str(config_path),
            "dry_run": args.dry_run,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "api_name": item["api_name"],
                    "base_url": item["base_url"],
                    "model": item["model"],
                    "api_key_env": item["api_key_env"],
                }
                for item in candidates
            ],
        },
    )

    if args.dry_run:
        write_json(
            run_dir / "summary.json",
            {
                "status": "dry_run",
                "chosen_model": None,
                "attempts": [],
                "run_dir": str(run_dir),
            },
        )
        print(f"Dry run wrote request plan to {run_dir}")
        return 0

    verifier = args.verify_command or (config.get("verifier") or {}).get("command", "")
    verifier_timeout = int((config.get("verifier") or {}).get("timeout_seconds", args.timeout))
    attempts: list[dict[str, Any]] = []
    chosen: str | None = None

    for candidate in candidates:
        attempt_dir = run_dir / "attempts" / model_slug(candidate["model"])
        attempt_dir.mkdir(parents=True, exist_ok=True)
        try:
            payload = call_chat_completion(candidate, messages, args.timeout)
            response_text = extract_message(payload)
            (attempt_dir / "response.md").write_text(response_text)
            (attempt_dir / "solution.py").write_text(extract_python_code(response_text))
            if verifier:
                result = run_verifier(verifier, attempt_dir, verifier_timeout)
                write_json(attempt_dir / "verifier.json", result)
                passed = bool(result["passed"])
            else:
                passed = True
            attempts.append(
                {
                    "model": candidate["model"],
                    "api_name": candidate["api_name"],
                    "passed": passed,
                    "attempt_dir": str(attempt_dir),
                }
            )
            if passed:
                chosen = candidate["model"]
                break
        except Exception as exc:  # noqa: BLE001 - demo should keep trying candidates.
            attempts.append(
                {
                    "model": candidate["model"],
                    "api_name": candidate["api_name"],
                    "passed": False,
                    "error": str(exc),
                    "attempt_dir": str(attempt_dir),
                }
            )

    status = "solved" if chosen else "failed"
    write_json(
        run_dir / "summary.json",
        {"status": status, "chosen_model": chosen, "attempts": attempts, "run_dir": str(run_dir)},
    )
    print(f"{status}: {chosen or 'no candidate passed'}")
    print(f"Run directory: {run_dir}")
    return 0 if chosen else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(here / "models.example.json"))
    parser.add_argument("--problem-file")
    parser.add_argument("--problem")
    parser.add_argument("--output-dir", default=str(here / "runs"))
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--verify-command", default="")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return solve(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
