"""Patch prediction loading utilities for SWE-bench style OOD runs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def patch_sha256(patch: str) -> str:
    return hashlib.sha256(patch.encode("utf-8")).hexdigest()


def safe_model_filename(model: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("._")
    if not name:
        raise ValueError(f"cannot build filename for empty model name: {model!r}")
    return name


def prediction_file(predictions_root: Path, model: str) -> Path:
    return predictions_root / f"{safe_model_filename(model)}.json"


def _items_from_payload(payload: Any) -> dict[str, dict]:
    if isinstance(payload, dict) and isinstance(payload.get("items"), dict):
        return payload["items"]
    if isinstance(payload, dict):
        items: dict[str, dict] = {}
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            instance_id = str(value.get("instance_id") or key)
            items[instance_id] = value
        return items
    if isinstance(payload, list):
        items = {}
        for value in payload:
            if not isinstance(value, dict):
                continue
            instance_id = value.get("instance_id")
            if instance_id:
                items[str(instance_id)] = value
        return items
    raise ValueError(f"unsupported prediction payload type: {type(payload).__name__}")


def load_model_predictions(predictions_root: Path, model: str) -> dict[str, dict]:
    path = prediction_file(predictions_root, model)
    with path.open() as f:
        payload = json.load(f)
    return _items_from_payload(payload)


class PatchStore:
    """Lazy loader for per-model SWE-bench patches."""

    def __init__(self, predictions_root: Path):
        self.predictions_root = Path(predictions_root)
        self._cache: dict[str, dict[str, dict]] = {}

    def items_for_model(self, model: str) -> dict[str, dict]:
        if model not in self._cache:
            self._cache[model] = load_model_predictions(self.predictions_root, model)
        return self._cache[model]

    def patch(self, task_id: str, model: str) -> str | None:
        item = self.items_for_model(model).get(task_id)
        if not item:
            return None
        patch = item.get("model_patch")
        if patch is None:
            patch = item.get("patch")
        return str(patch) if patch is not None else None

