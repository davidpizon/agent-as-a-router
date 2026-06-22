"""Trained router baselines: LogReg and BERT/MLP routers.

These routers learn from oracle labels to predict the best backend model
for a given task, using features extracted from the task prompt and metadata.

Classes:
    LogRegRouter  -- TF-IDF + dimension one-hot + prompt length -> LogisticRegression
    BERTMLPRouter -- Sentence-transformer embeddings (or TF-IDF fallback) -> MLP classifier
"""
import hashlib
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from .base import BACKEND_MODELS, BaseRouter, RoutingDecision
from .data_manager import DataManager

import os

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODEL_DIR = _PROJECT_ROOT / "data" / "routing" / "trained_models"


# ---------------------------------------------------------------------------
# Feature extraction utilities
# ---------------------------------------------------------------------------

def _get_all_dimensions(dm: DataManager) -> list[str]:
    """Collect sorted list of unique dimensions from training data."""
    dims = set()
    for task_id in dm.train:
        task = dm.get_task(task_id)
        if task:
            dims.add(task.get("dimension", "unknown"))
    return sorted(dims)


def _build_labels(dm: DataManager, task_ids: list[str]) -> tuple[list[str], dict[str, int]]:
    """Build oracle labels (model names) for a list of task IDs.

    Returns:
        labels: list of model name strings (one per task).
        label_map: str -> int mapping of model name to class index.
    """
    label_map = {m: i for i, m in enumerate(BACKEND_MODELS)}
    labels = []
    for task_id in task_ids:
        best = dm.get_oracle_model(task_id)
        labels.append(best)
    return labels, label_map


# ---------------------------------------------------------------------------
# LogReg Router
# ---------------------------------------------------------------------------

class LogRegRouter(BaseRouter):
    """Logistic Regression router.

    Features:
        - TF-IDF on the task prompt (max 5000 features)
        - One-hot encoding of the task dimension
        - Normalized prompt length (character count / 10000)

    Uses sklearn LogisticRegression with multiclass 'ovr' strategy.
    """

    def __init__(
        self,
        model_dir: Path = _DEFAULT_MODEL_DIR,
        max_tfidf_features: int = 5000,
    ):
        self.model_dir = Path(model_dir)
        self.max_tfidf_features = max_tfidf_features

        # Fitted components (populated by train() or load())
        self._tfidf = None          # TfidfVectorizer
        self._clf = None            # LogisticRegression
        self._dimensions: list[str] = []   # sorted dimension names
        self._label_map: dict[str, int] = {}
        self._inv_label_map: dict[int, str] = {}

    @property
    def name(self) -> str:
        return "logreg"

    # ----- Feature extraction -----

    def _extract_features(self, tasks: list[dict], fit: bool = False) -> np.ndarray:
        """Build feature matrix from a list of task dicts.

        Args:
            tasks: list of sanitized task dicts.
            fit: if True, fit the TF-IDF vectorizer (training time only).

        Returns:
            Feature matrix of shape (n_tasks, n_features).
        """
        from scipy.sparse import hstack, csr_matrix

        prompts = [t.get("prompt", "") for t in tasks]

        # TF-IDF features
        if fit:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf = TfidfVectorizer(
                max_features=self.max_tfidf_features,
                sublinear_tf=True,
                strip_accents="unicode",
                analyzer="word",
                token_pattern=r"(?u)\b\w+\b",
                ngram_range=(1, 2),
            )
            tfidf_matrix = self._tfidf.fit_transform(prompts)
        else:
            tfidf_matrix = self._tfidf.transform(prompts)

        # Dimension one-hot
        dim_indices = {d: i for i, d in enumerate(self._dimensions)}
        n_dims = len(self._dimensions)
        dim_onehot = np.zeros((len(tasks), n_dims), dtype=np.float64)
        for i, t in enumerate(tasks):
            d = t.get("dimension", "unknown")
            if d in dim_indices:
                dim_onehot[i, dim_indices[d]] = 1.0

        # Prompt length (normalized)
        lengths = np.array(
            [len(t.get("prompt", "")) / 10000.0 for t in tasks],
            dtype=np.float64,
        ).reshape(-1, 1)

        # Combine all features
        extra = np.hstack([dim_onehot, lengths])
        combined = hstack([tfidf_matrix, csr_matrix(extra)])
        return combined

    # ----- Training -----

    def train(self, dm: DataManager) -> "LogRegRouter":
        """Train the LogReg router on the training split.

        Args:
            dm: A loaded DataManager instance.

        Returns:
            self (for chaining).
        """
        from sklearn.linear_model import LogisticRegression

        self._dimensions = _get_all_dimensions(dm)
        labels, self._label_map = _build_labels(dm, dm.train)
        self._inv_label_map = {v: k for k, v in self._label_map.items()}

        # Collect tasks
        tasks = []
        valid_labels = []
        for task_id, label in zip(dm.train, labels):
            task = dm.get_task(task_id)
            if task is not None:
                tasks.append(task)
                valid_labels.append(self._label_map[label])

        logger.info("LogRegRouter: extracting features for %d training tasks", len(tasks))
        X = self._extract_features(tasks, fit=True)
        y = np.array(valid_labels)

        logger.info("LogRegRouter: training LogisticRegression (C=1.0, max_iter=1000)")
        self._clf = LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            n_jobs=-1,
        )
        self._clf.fit(X, y)
        logger.info("LogRegRouter: training complete")
        return self

    # ----- Prediction (routing) -----

    async def route(self, task: dict) -> RoutingDecision:
        """Route a single task using the trained LogReg model."""
        if self._clf is None:
            raise RuntimeError("LogRegRouter has not been trained or loaded. Call train() or load() first.")

        sanitized = self._sanitize_task(task)
        X = self._extract_features([sanitized], fit=False)
        pred_idx = int(self._clf.predict(X)[0])
        proba = self._clf.predict_proba(X)[0]
        confidence = float(proba[pred_idx])
        chosen = self._inv_label_map.get(pred_idx, BACKEND_MODELS[0])

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=confidence,
            reasoning=f"LogReg prediction (confidence={confidence:.3f})",
        )

    # ----- Save / Load -----

    def save(self, path: Optional[Path] = None):
        """Persist the trained model to disk."""
        path = Path(path) if path else self.model_dir / "logreg_router.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "tfidf": self._tfidf,
            "clf": self._clf,
            "dimensions": self._dimensions,
            "label_map": self._label_map,
            "inv_label_map": self._inv_label_map,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)
        logger.info("LogRegRouter: saved to %s", path)

    def load(self, path: Optional[Path] = None) -> "LogRegRouter":
        """Load a previously trained model from disk."""
        path = Path(path) if path else self.model_dir / "logreg_router.pkl"
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._tfidf = state["tfidf"]
        self._clf = state["clf"]
        self._dimensions = state["dimensions"]
        self._label_map = state["label_map"]
        self._inv_label_map = state["inv_label_map"]
        logger.info("LogRegRouter: loaded from %s", path)
        return self


# ---------------------------------------------------------------------------
# BERT / MLP Router
# ---------------------------------------------------------------------------

class BERTMLPRouter(BaseRouter):
    """BERT (sentence-transformer) + MLP router.

    Attempts to use `sentence-transformers` to embed prompts with
    ``all-MiniLM-L6-v2``.  If the library is not installed, falls back to
    TF-IDF + sklearn MLPClassifier, providing comparable functionality
    without a GPU or large dependencies.

    The MLP head is always an sklearn MLPClassifier with one hidden layer.
    """

    def __init__(
        self,
        model_dir: Path = _DEFAULT_MODEL_DIR,
        st_model_name: str = os.environ.get(
            "ST_MODEL_PATH", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        max_tfidf_features: int = 5000,
    ):
        self.model_dir = Path(model_dir)
        self.st_model_name = st_model_name
        self.max_tfidf_features = max_tfidf_features

        # Internal state
        self._use_sentence_transformers: bool = False
        self._st_model = None        # SentenceTransformer (if available)
        self._tfidf = None           # TfidfVectorizer (fallback)
        self._clf = None             # MLPClassifier
        self._dimensions: list[str] = []
        self._label_map: dict[str, int] = {}
        self._inv_label_map: dict[int, str] = {}

    @property
    def name(self) -> str:
        return "bert_mlp" if self._use_sentence_transformers else "tfidf_mlp"

    # ----- Embedding -----

    def _try_load_sentence_transformer(self) -> bool:
        """Attempt to load the sentence-transformer model.

        Returns True if successful, False otherwise (fallback to TF-IDF).
        """
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("BERTMLPRouter: loading sentence-transformer model '%s'", self.st_model_name)
            self._st_model = SentenceTransformer(self.st_model_name)
            # Verify the model can encode a test sentence
            self._st_model.encode(["test"], show_progress_bar=False)
            self._use_sentence_transformers = True
            logger.info("BERTMLPRouter: sentence-transformer loaded successfully, using BERT embeddings")
            return True
        except ImportError:
            logger.info(
                "BERTMLPRouter: sentence-transformers not installed, "
                "falling back to TF-IDF + MLP"
            )
            self._use_sentence_transformers = False
            return False
        except Exception as e:
            logger.warning(
                "BERTMLPRouter: sentence-transformer failed (%s: %s), "
                "falling back to TF-IDF + MLP",
                type(e).__name__, e,
            )
            self._st_model = None
            self._use_sentence_transformers = False
            return False

    def _embed(self, tasks: list[dict], fit: bool = False) -> np.ndarray:
        """Produce embeddings for a list of tasks.

        When sentence-transformers is available, embeddings come from the
        pre-trained model.  Otherwise, TF-IDF vectors are used.

        Extra features (dimension one-hot, prompt length) are always appended.

        Args:
            tasks: list of sanitized task dicts.
            fit: whether to fit vectorizers (training time).

        Returns:
            np.ndarray of shape (n_tasks, embed_dim).
        """
        prompts = [t.get("prompt", "") for t in tasks]

        if self._use_sentence_transformers and self._st_model is not None:
            # Sentence-transformer embeddings
            embeddings = self._st_model.encode(
                prompts, show_progress_bar=False, batch_size=64,
            )
            embeddings = np.asarray(embeddings, dtype=np.float64)
        else:
            # TF-IDF fallback
            if fit:
                from sklearn.feature_extraction.text import TfidfVectorizer
                self._tfidf = TfidfVectorizer(
                    max_features=self.max_tfidf_features,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    analyzer="word",
                    token_pattern=r"(?u)\b\w+\b",
                    ngram_range=(1, 2),
                )
                tfidf_matrix = self._tfidf.fit_transform(prompts)
            else:
                tfidf_matrix = self._tfidf.transform(prompts)
            # Convert sparse to dense for MLP
            embeddings = tfidf_matrix.toarray().astype(np.float64)

        # Append dimension one-hot + prompt length
        dim_indices = {d: i for i, d in enumerate(self._dimensions)}
        n_dims = len(self._dimensions)
        dim_onehot = np.zeros((len(tasks), n_dims), dtype=np.float64)
        for i, t in enumerate(tasks):
            d = t.get("dimension", "unknown")
            if d in dim_indices:
                dim_onehot[i, dim_indices[d]] = 1.0

        lengths = np.array(
            [len(t.get("prompt", "")) / 10000.0 for t in tasks],
            dtype=np.float64,
        ).reshape(-1, 1)

        return np.hstack([embeddings, dim_onehot, lengths])

    # ----- Training -----

    def train(self, dm: DataManager) -> "BERTMLPRouter":
        """Train the BERT/MLP router on the training split.

        Args:
            dm: A loaded DataManager instance.

        Returns:
            self (for chaining).
        """
        from sklearn.neural_network import MLPClassifier

        self._dimensions = _get_all_dimensions(dm)
        labels, self._label_map = _build_labels(dm, dm.train)
        self._inv_label_map = {v: k for k, v in self._label_map.items()}

        # Try sentence-transformers; fall back to TF-IDF
        self._try_load_sentence_transformer()

        # Collect tasks
        tasks = []
        valid_labels = []
        for task_id, label in zip(dm.train, labels):
            task = dm.get_task(task_id)
            if task is not None:
                tasks.append(task)
                valid_labels.append(self._label_map[label])

        embed_name = "sentence-transformer" if self._use_sentence_transformers else "TF-IDF"
        logger.info("BERTMLPRouter: embedding %d training tasks with %s", len(tasks), embed_name)
        X = self._embed(tasks, fit=True)
        y = np.array(valid_labels)

        logger.info("BERTMLPRouter: training MLPClassifier (hidden=256, max_iter=500)")
        self._clf = MLPClassifier(
            hidden_layer_sizes=(256,),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=42,
            batch_size=min(256, max(32, len(tasks) // 10)),
        )
        self._clf.fit(X, y)
        logger.info("BERTMLPRouter: training complete (backend=%s)", embed_name)
        return self

    # ----- Prediction (routing) -----

    async def route(self, task: dict) -> RoutingDecision:
        """Route a single task using the trained BERT/MLP model."""
        if self._clf is None:
            raise RuntimeError("BERTMLPRouter has not been trained or loaded. Call train() or load() first.")

        sanitized = self._sanitize_task(task)
        X = self._embed([sanitized], fit=False)
        pred_idx = int(self._clf.predict(X)[0])
        proba = self._clf.predict_proba(X)[0]
        confidence = float(proba[pred_idx])
        chosen = self._inv_label_map.get(pred_idx, BACKEND_MODELS[0])

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=confidence,
            reasoning=f"{self.name} prediction (confidence={confidence:.3f})",
        )

    # ----- Save / Load -----

    def save(self, path: Optional[Path] = None):
        """Persist the trained model to disk.

        Note: the sentence-transformer model itself is not saved (it is loaded
        from HuggingFace cache at load time).  Only the MLP head, vectorizer,
        and metadata are persisted.
        """
        path = Path(path) if path else self.model_dir / "bert_mlp_router.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "use_sentence_transformers": self._use_sentence_transformers,
            "st_model_name": self.st_model_name,
            "tfidf": self._tfidf,
            "clf": self._clf,
            "dimensions": self._dimensions,
            "label_map": self._label_map,
            "inv_label_map": self._inv_label_map,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)
        logger.info("BERTMLPRouter: saved to %s", path)

    def load(self, path: Optional[Path] = None) -> "BERTMLPRouter":
        """Load a previously trained model from disk.

        If the model was trained with sentence-transformers, this method will
        attempt to reload the sentence-transformer model.  If the library is
        not available, it will fail (since the TF-IDF vectorizer was not saved
        in that case).
        """
        path = Path(path) if path else self.model_dir / "bert_mlp_router.pkl"
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._use_sentence_transformers = state["use_sentence_transformers"]
        self.st_model_name = state["st_model_name"]
        self._tfidf = state["tfidf"]
        self._clf = state["clf"]
        self._dimensions = state["dimensions"]
        self._label_map = state["label_map"]
        self._inv_label_map = state["inv_label_map"]

        # Reload sentence-transformer if needed
        if self._use_sentence_transformers:
            if not self._try_load_sentence_transformer():
                raise RuntimeError(
                    "Model was trained with sentence-transformers but the library "
                    "is not installed. Install with: pip install sentence-transformers"
                )
        logger.info("BERTMLPRouter: loaded from %s (backend=%s)",
                     path, "sentence-transformer" if self._use_sentence_transformers else "TF-IDF")
        return self
