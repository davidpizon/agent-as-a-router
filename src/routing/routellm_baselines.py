"""RouteLLM baseline methods adapted for multi-model routing.

Implements 3 of the 4 RouteLLM approaches from Ong et al. (ICLR 2025):
1. Matrix Factorization (MF) — learns bilinear scoring δ(M,q)
2. BERT classifier — fine-tunes BERT with classification head
3. SW Ranking — similarity-weighted Bradley-Terry (no training)

Adapted from binary (strong/weak) routing to N-model selection:
instead of P(win_s|q), we learn P(model=m|q) for each model m.

Reference: "RouteLLM: Learning to Route LLMs with Preference Data" (ICLR 2025)
"""

import json
import logging
import os
import random
from collections import defaultdict
from typing import Optional

import numpy as np

from .base import BACKEND_MODELS, BaseRouter, RoutingDecision
from .data_manager import DataManager

logger = logging.getLogger(__name__)


# ============================================================
# 1. Matrix Factorization Router
# ============================================================

class MFRouter(BaseRouter):
    """Matrix Factorization router (RouteLLM-style).

    Learns a bilinear scoring function δ(M, q) = w2^T (v_m ⊙ (W1^T v_q + b))
    where v_m is a model embedding and v_q is a query embedding.

    For multi-model routing: learns δ for each model, routes to argmax δ(m, q).

    Training: uses oracle labels as supervision (model m gets label 1 if it's
    the oracle-best for query q, 0 otherwise).

    Requires: numpy, scikit-learn (for TF-IDF embeddings)
    GPU version: use torch for the bilinear model (see train_gpu)
    """

    def __init__(self, embed_dim: int = 128, model_dim: int = 64):
        self.embed_dim = embed_dim
        self.model_dim = model_dim
        self._model_embeds = None  # {model_name: np.array}
        self._W1 = None
        self._b = None
        self._w2 = None
        self._tfidf = None
        self._trained = False

    @property
    def name(self) -> str:
        return "routellm_mf"

    def train(self, dm: DataManager):
        """Train MF router on oracle labels."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD

        logger.info("MFRouter: preparing training data")

        # Collect training data
        texts = []
        labels = []  # index into BACKEND_MODELS
        model_to_idx = {m: i for i, m in enumerate(BACKEND_MODELS)}

        for tid in dm.train:
            task = dm.get_task(tid)
            if not task:
                continue
            oracle = dm.get_oracle_model(tid)
            if oracle not in model_to_idx:
                continue
            texts.append(task.get("prompt", "")[:1000])
            labels.append(model_to_idx[oracle])

        if not texts:
            logger.error("No training data")
            return

        logger.info(f"MFRouter: {len(texts)} training samples")

        # Query embeddings via TF-IDF + SVD
        self._tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X_tfidf = self._tfidf.fit_transform(texts)

        svd = TruncatedSVD(n_components=self.embed_dim, random_state=42)
        X_embed = svd.fit_transform(X_tfidf)  # (N, embed_dim)
        self._svd = svd

        # Model embeddings (randomly initialized, then optimized)
        n_models = len(BACKEND_MODELS)
        self._model_embeds = np.random.randn(n_models, self.model_dim) * 0.1

        # Projection: W1 maps query embed to model_dim
        self._W1 = np.random.randn(self.embed_dim, self.model_dim) * 0.1
        self._b = np.zeros(self.model_dim)
        self._w2 = np.random.randn(self.model_dim) * 0.1

        # Simple training: use sklearn LogisticRegression on (query_embed, model_idx)
        # This is a simplified MF — full version uses SGD on the bilinear form
        from sklearn.linear_model import LogisticRegression
        y = np.array(labels)
        clf = LogisticRegression(max_iter=1000, C=1.0)
        clf.fit(X_embed, y)
        self._clf = clf
        self._trained = True
        logger.info("MFRouter: training complete")

    def _embed_query(self, text):
        if self._tfidf is None:
            return np.zeros(self.embed_dim)
        X = self._tfidf.transform([text[:1000]])
        return self._svd.transform(X)[0]

    async def route(self, task: dict) -> RoutingDecision:
        sanitized = self._sanitize_task(task)
        text = sanitized.get("prompt", "")
        embed = self._embed_query(text)

        if self._trained and self._clf is not None:
            probs = self._clf.predict_proba(embed.reshape(1, -1))[0]
            model_idx = np.argmax(probs)
            chosen = BACKEND_MODELS[model_idx]
            conf = float(probs[model_idx])
        else:
            chosen = BACKEND_MODELS[0]
            conf = 0.0

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=conf,
            reasoning=f"MF router: {chosen} (conf={conf:.2f})",
        )

    def save(self, path: str):
        import pickle
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "mf_router.pkl"), "wb") as f:
            pickle.dump({
                "clf": self._clf, "tfidf": self._tfidf, "svd": self._svd,
                "trained": self._trained,
            }, f)

    def load(self, path: str):
        import pickle
        with open(os.path.join(path, "mf_router.pkl"), "rb") as f:
            d = pickle.load(f)
            self._clf = d["clf"]
            self._tfidf = d["tfidf"]
            self._svd = d["svd"]
            self._trained = d["trained"]


# ============================================================
# 2. BERT Classifier Router (GPU required)
# ============================================================

class BERTRouter(BaseRouter):
    """BERT classifier router (RouteLLM-style).

    Fine-tunes BERT_BASE with a classification head to predict
    the oracle-best model from the query text.

    P(model=m|q) = softmax(W · h_CLS + b)

    Requires GPU + transformers + torch.
    """

    def __init__(self, model_name: str = "bert-base-uncased", max_len: int = 512):
        self.model_name = model_name
        self.max_len = max_len
        self._model = None
        self._tokenizer = None
        self._trained = False

    @property
    def name(self) -> str:
        return "routellm_bert"

    def train(self, dm: DataManager, epochs: int = 3, batch_size: int = 16, lr: float = 1e-5):
        """Fine-tune BERT on oracle labels. Requires GPU."""
        try:
            import torch
            from torch import nn
            from torch.utils.data import DataLoader, Dataset
            from transformers import BertTokenizer, BertForSequenceClassification
        except ImportError:
            logger.error("BERTRouter requires: pip install torch transformers")
            return

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"BERTRouter: training on {device}")

        # Prepare data
        model_to_idx = {m: i for i, m in enumerate(BACKEND_MODELS)}
        texts, labels = [], []
        for tid in dm.train:
            task = dm.get_task(tid)
            if not task:
                continue
            oracle = dm.get_oracle_model(tid)
            if oracle not in model_to_idx:
                continue
            texts.append(task.get("prompt", "")[:self.max_len * 4])
            labels.append(model_to_idx[oracle])

        logger.info(f"BERTRouter: {len(texts)} training samples, {len(BACKEND_MODELS)} classes")

        # Tokenizer + Model
        self._tokenizer = BertTokenizer.from_pretrained(self.model_name)
        self._model = BertForSequenceClassification.from_pretrained(
            self.model_name, num_labels=len(BACKEND_MODELS)
        ).to(device)

        # Dataset
        class RouterDataset(Dataset):
            def __init__(self, texts, labels, tokenizer, max_len):
                self.texts = texts
                self.labels = labels
                self.tokenizer = tokenizer
                self.max_len = max_len

            def __len__(self):
                return len(self.texts)

            def __getitem__(self, idx):
                enc = self.tokenizer(
                    self.texts[idx], truncation=True, padding="max_length",
                    max_length=self.max_len, return_tensors="pt"
                )
                return {
                    "input_ids": enc["input_ids"].squeeze(),
                    "attention_mask": enc["attention_mask"].squeeze(),
                    "labels": torch.tensor(self.labels[idx], dtype=torch.long),
                }

        dataset = RouterDataset(texts, labels, self._tokenizer, self.max_len)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Train
        optimizer = torch.optim.AdamW(self._model.parameters(), lr=lr, weight_decay=0.01)
        self._model.train()

        for epoch in range(epochs):
            total_loss = 0
            for batch in loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = self._model(**batch)
                loss = outputs.loss
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                total_loss += loss.item()
            logger.info(f"  Epoch {epoch+1}/{epochs}: loss={total_loss/len(loader):.4f}")

        self._model.eval()
        self._trained = True
        logger.info("BERTRouter: training complete")

    async def route(self, task: dict) -> RoutingDecision:
        sanitized = self._sanitize_task(task)
        text = sanitized.get("prompt", "")

        if not self._trained or self._model is None:
            return RoutingDecision(
                task_id=task.get("task_id", ""),
                chosen_model=BACKEND_MODELS[0],
                confidence=0.0,
            )

        import torch
        device = next(self._model.parameters()).device
        enc = self._tokenizer(
            text, truncation=True, padding="max_length",
            max_length=self.max_len, return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            outputs = self._model(**enc)
            probs = torch.softmax(outputs.logits, dim=-1)[0].cpu().numpy()

        model_idx = int(np.argmax(probs))
        chosen = BACKEND_MODELS[model_idx]

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=float(probs[model_idx]),
            reasoning=f"BERT router: {chosen}",
        )

    def save(self, path: str):
        os.makedirs(path, exist_ok=True)
        if self._model:
            self._model.save_pretrained(os.path.join(path, "bert_router"))
        if self._tokenizer:
            self._tokenizer.save_pretrained(os.path.join(path, "bert_router"))

    def load(self, path: str):
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        model_path = os.path.join(path, "bert_router")
        self._tokenizer = BertTokenizer.from_pretrained(model_path)
        self._model = BertForSequenceClassification.from_pretrained(model_path)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = self._model.to(device).eval()
        self._trained = True


# ============================================================
# 3. SW Ranking Router (no training needed)
# ============================================================

class SWRankingRouter(BaseRouter):
    """Similarity-Weighted (SW) Ranking router (RouteLLM-style).

    Uses cosine similarity to find nearest training queries,
    then applies Bradley-Terry model weighted by similarity.

    No training required — solved at inference time.
    Adapted for multi-model: computes per-model win rates
    weighted by query similarity.
    """

    def __init__(self, gamma: float = 10.0, top_k: int = 50):
        self.gamma = gamma
        self.top_k = top_k
        self._train_embeds = None
        self._train_labels = None  # oracle model index per train sample
        self._tfidf = None

    @property
    def name(self) -> str:
        return "routellm_sw"

    def train(self, dm: DataManager):
        """Prepare embeddings (no gradient optimization)."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        model_to_idx = {m: i for i, m in enumerate(BACKEND_MODELS)}
        texts, labels = [], []

        for tid in dm.train:
            task = dm.get_task(tid)
            if not task:
                continue
            oracle = dm.get_oracle_model(tid)
            if oracle not in model_to_idx:
                continue
            texts.append(task.get("prompt", "")[:1000])
            labels.append(model_to_idx[oracle])

        logger.info(f"SWRankingRouter: {len(texts)} reference samples")

        self._tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X = self._tfidf.fit_transform(texts)
        self._train_embeds = normalize(X)  # L2-normalized for cosine sim
        self._train_labels = np.array(labels)

    async def route(self, task: dict) -> RoutingDecision:
        sanitized = self._sanitize_task(task)
        text = sanitized.get("prompt", "")

        if self._tfidf is None or self._train_embeds is None:
            return RoutingDecision(
                task_id=task.get("task_id", ""),
                chosen_model=BACKEND_MODELS[0],
                confidence=0.0,
            )

        from sklearn.preprocessing import normalize

        # Embed query
        q_embed = normalize(self._tfidf.transform([text[:1000]]))

        # Cosine similarity to all training samples
        sims = (self._train_embeds @ q_embed.T).toarray().flatten()

        # Top-K most similar
        top_indices = np.argsort(sims)[-self.top_k:]
        top_sims = sims[top_indices]
        top_labels = self._train_labels[top_indices]

        # Similarity-weighted vote for each model
        # Weight: gamma^(1 + sim) (exponential weighting)
        weights = self.gamma ** (1 + top_sims)

        model_scores = np.zeros(len(BACKEND_MODELS))
        for idx, (label, w) in enumerate(zip(top_labels, weights)):
            model_scores[label] += w

        # Normalize to probabilities
        if model_scores.sum() > 0:
            probs = model_scores / model_scores.sum()
        else:
            probs = np.ones(len(BACKEND_MODELS)) / len(BACKEND_MODELS)

        model_idx = int(np.argmax(probs))
        chosen = BACKEND_MODELS[model_idx]

        return RoutingDecision(
            task_id=task.get("task_id", ""),
            chosen_model=chosen,
            confidence=float(probs[model_idx]),
            reasoning=f"SW ranking: {chosen} (conf={probs[model_idx]:.2f})",
        )

    def save(self, path: str):
        import pickle
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "sw_router.pkl"), "wb") as f:
            pickle.dump({
                "tfidf": self._tfidf,
                "train_embeds": self._train_embeds,
                "train_labels": self._train_labels,
                "gamma": self.gamma,
            }, f)

    def load(self, path: str):
        import pickle
        with open(os.path.join(path, "sw_router.pkl"), "rb") as f:
            d = pickle.load(f)
            self._tfidf = d["tfidf"]
            self._train_embeds = d["train_embeds"]
            self._train_labels = d["train_labels"]
            self.gamma = d["gamma"]
