"""Helpers for using the Hugging Face CodeRouterBench release."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path
import shutil
from typing import Iterable
from urllib.request import Request, urlopen
import warnings


DEFAULT_DATASET_REPO_ID = "Lance1573/CodeRouterBench"
DEFAULT_DATASET_REPO_TYPE = "dataset"
DEFAULT_DATASET_DIR = Path(".hf") / "CodeRouterBench"
DEFAULT_ROUTER_MODEL_REPO_ID = "Lance1573/acrouter-qwen35-08b-router-lora"
DEFAULT_ROUTER_MODEL_DIR = Path(".hf") / "router_model"
MINIMAL_DATASET_PATTERNS = (
    "summary.json",
    "models.json",
    "ood176_results_long.csv",
    "ood176_tasks.jsonl",
    "raw_matrices/phase2_ood/unified/matrix_acrouter_ood176.json",
    "raw_matrices/phase2_ood/unified/summary.json",
    "raw_matrices/phase2_ood/unified/tasks.jsonl",
)

HF_OOD_MATRIX = Path("raw_matrices/phase2_ood/unified/matrix_acrouter_ood176.json")
HF_OOD_TASKS = Path("raw_matrices/phase2_ood/unified/tasks.jsonl")
HF_CANONICAL_FILES = (
    Path("summary.json"),
    Path("models.json"),
    Path("id_results_long.csv"),
    Path("id_probing_results_long.csv"),
    Path("id_test_results_long.csv"),
    Path("ood176_results_long.csv"),
    Path("id_tasks.jsonl"),
    Path("id_probing_tasks.jsonl"),
    Path("id_test_tasks.jsonl"),
    Path("ood176_tasks.jsonl"),
)

LOCAL_OOD_MATRIX = Path("data/matrices/phase2_ood/unified/matrix_acrouter_ood176.json")


@dataclass(frozen=True)
class HFAssetLayout:
    """Resolved paths inside a downloaded CodeRouterBench snapshot."""

    root: Path
    ood_matrix: Path
    summary: Path
    models: Path


def default_dataset_dir(repo_root: Path) -> Path:
    return repo_root / DEFAULT_DATASET_DIR


def format_path(path: Path, repo_root: Path) -> str:
    """Return a stable relative path when possible, otherwise an absolute path."""

    resolved = path.resolve()
    root = repo_root.resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _env_dataset_dir() -> Path | None:
    value = os.environ.get("ACROUTER_HF_DATASET_DIR")
    return Path(value).expanduser() if value else None


def _candidate_dataset_dir(hf_dataset_dir: Path | None) -> Path | None:
    if hf_dataset_dir is not None:
        return Path(hf_dataset_dir).expanduser()
    return _env_dataset_dir()


def resolve_hf_layout(hf_dataset_dir: Path) -> HFAssetLayout:
    """Validate and return the key paths in a downloaded HF dataset snapshot."""

    root = Path(hf_dataset_dir).expanduser()
    ood_matrix = root / HF_OOD_MATRIX
    summary = root / "summary.json"
    models = root / "models.json"
    missing = [path for path in [ood_matrix, summary, models] if not path.exists()]
    if missing:
        missing_list = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            "Downloaded CodeRouterBench snapshot is missing required files:\n"
            f"{missing_list}\n"
            "Download the full dataset with:\n"
            f"  hf download {DEFAULT_DATASET_REPO_ID} --repo-type dataset --local-dir {root}"
        )
    return HFAssetLayout(root=root, ood_matrix=ood_matrix, summary=summary, models=models)


def resolve_ood_matrix(
    repo_root: Path,
    matrix: Path | None = None,
    hf_dataset_dir: Path | None = None,
) -> Path:
    """Resolve the OOD176 matrix from an explicit path, HF snapshot, or bundle."""

    if matrix is not None:
        return Path(matrix).expanduser()

    dataset_dir = _candidate_dataset_dir(hf_dataset_dir)
    if dataset_dir is not None:
        return resolve_hf_layout(dataset_dir).ood_matrix

    return repo_root / LOCAL_OOD_MATRIX


def download_snapshot(
    repo_id: str,
    local_dir: Path,
    repo_type: str,
    revision: str | None = None,
    allow_patterns: Iterable[str] | None = None,
    token: str | None = None,
    max_workers: int = 1,
) -> Path:
    """Download a Hugging Face snapshot into a local directory."""

    try:
        from huggingface_hub import HfApi, hf_hub_url, snapshot_download
    except ImportError as exc:  # pragma: no cover - exercised by user envs.
        raise RuntimeError(
            "Missing huggingface_hub. Install it with: "
            "python -m pip install -U huggingface_hub"
        ) from exc

    destination = Path(local_dir).expanduser()
    patterns = list(allow_patterns) if allow_patterns else None
    try:
        path = snapshot_download(
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
            local_dir=str(destination),
            allow_patterns=patterns,
            token=token,
            max_workers=max_workers,
        )
        return Path(path)
    except Exception as exc:
        warnings.warn(
            "huggingface_hub.snapshot_download failed; falling back to a "
            f"standard-library file downloader: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return _download_files_with_urllib(
            api=HfApi(token=token),
            hf_hub_url=hf_hub_url,
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
            local_dir=destination,
            allow_patterns=patterns,
            token=token,
        )


def _matches_any(path: str, patterns: Iterable[str] | None) -> bool:
    if patterns is None:
        return True
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _download_files_with_urllib(
    api,
    hf_hub_url,
    repo_id: str,
    repo_type: str,
    revision: str | None,
    local_dir: Path,
    allow_patterns: Iterable[str] | None,
    token: str | None,
) -> Path:
    """Fallback downloader that avoids httpx/brotli decoding issues."""

    local_dir.mkdir(parents=True, exist_ok=True)
    files = api.list_repo_files(repo_id=repo_id, repo_type=repo_type, revision=revision)
    selected = [path for path in files if _matches_any(path, allow_patterns)]
    if not selected:
        raise FileNotFoundError(
            f"No files matched {list(allow_patterns or [])} in {repo_type} repo {repo_id}"
        )

    headers = {
        "Accept-Encoding": "identity",
        "User-Agent": "acrouter-repro-hf-downloader",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for filename in selected:
        url = hf_hub_url(
            repo_id=repo_id,
            filename=filename,
            repo_type=repo_type,
            revision=revision,
        )
        target = local_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers=headers)
        with urlopen(request) as response, target.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return local_dir


def download_coderouterbench(
    local_dir: Path,
    repo_id: str = DEFAULT_DATASET_REPO_ID,
    revision: str | None = None,
    allow_patterns: Iterable[str] | None = None,
    token: str | None = None,
    max_workers: int = 1,
) -> HFAssetLayout:
    """Download CodeRouterBench and return the resolved local layout."""

    root = download_snapshot(
        repo_id=repo_id,
        repo_type=DEFAULT_DATASET_REPO_TYPE,
        revision=revision,
        local_dir=local_dir,
        allow_patterns=allow_patterns,
        token=token,
        max_workers=max_workers,
    )
    return resolve_hf_layout(root)


def download_router_model(
    repo_id: str,
    local_dir: Path,
    revision: str | None = None,
    token: str | None = None,
    max_workers: int = 1,
) -> Path:
    """Download an optional public router model snapshot."""

    return download_snapshot(
        repo_id=repo_id,
        repo_type="model",
        revision=revision,
        local_dir=local_dir,
        token=token,
        max_workers=max_workers,
    )
