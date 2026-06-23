from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acrouter_repro.hf_assets import (
    DEFAULT_DATASET_REPO_ID,
    HF_OOD_MATRIX,
    format_path,
    resolve_hf_layout,
    resolve_ood_matrix,
)


class HFAssetTests(unittest.TestCase):
    def test_resolve_ood_matrix_prefers_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "matrix.json"
            explicit.write_text("{}\n")
            resolved = resolve_ood_matrix(
                repo_root=root,
                matrix=explicit,
                hf_dataset_dir=root / "missing",
            )
            self.assertEqual(resolved, explicit)

    def test_resolve_hf_layout_uses_uploaded_dataset_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = root / HF_OOD_MATRIX
            matrix.parent.mkdir(parents=True)
            matrix.write_text("{}\n")
            (root / "summary.json").write_text("{}\n")
            (root / "models.json").write_text("{}\n")

            layout = resolve_hf_layout(root)
            self.assertEqual(layout.root, root)
            self.assertEqual(layout.ood_matrix, matrix)
            self.assertEqual(resolve_ood_matrix(repo_root=root, hf_dataset_dir=root), matrix)

    def test_missing_hf_files_explain_download_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(FileNotFoundError, DEFAULT_DATASET_REPO_ID):
                resolve_hf_layout(root)

    def test_format_path_uses_repo_relative_paths_when_possible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data" / "x.json"
            self.assertEqual(format_path(path, root), "data/x.json")


if __name__ == "__main__":
    unittest.main()
