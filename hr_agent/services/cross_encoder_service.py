"""
Cross-encoder reranking service (Phase 4).

Scores job–candidate pairs jointly for higher precision than bi-encoder cosine
similarity alone. Uses sentence-transformers CrossEncoder when enabled.
"""
from __future__ import annotations

import logging

import numpy as np

from hr_agent.config import Settings

logger = logging.getLogger(__name__)

_cross_encoder_model = None


class CrossEncoderService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = settings.cross_encoder_enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        """
        Score each (query, document) pair. Returns values in [0, 1].
        Falls back to zeros when disabled or model unavailable.
        """
        if not documents:
            return []

        if not self._enabled:
            logger.debug("[RERANK-CE] Cross-encoder disabled — returning neutral scores.")
            return [0.5] * len(documents)

        model = self._load_model()
        if model is None:
            return [0.5] * len(documents)

        pairs = [(query, doc) for doc in documents]
        try:
            raw = model.predict(pairs, show_progress_bar=False)
            scores = np.array(raw, dtype=np.float64)
            normalized = self._normalize_batch(scores)
            logger.info(
                "[RERANK-CE] Scored %d pairs — min=%.3f max=%.3f mean=%.3f",
                len(documents), normalized.min(), normalized.max(), normalized.mean(),
            )
            return [round(float(s), 4) for s in normalized]
        except Exception as exc:
            logger.error("[RERANK-CE] Prediction failed: %s", exc)
            return [0.5] * len(documents)

    def _load_model(self):
        global _cross_encoder_model
        if _cross_encoder_model is not None:
            return _cross_encoder_model

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            logger.warning(
                "[RERANK-CE] sentence-transformers not installed — "
                "pip install sentence-transformers to enable cross-encoder rerank."
            )
            return None

        try:
            logger.info(
                "[RERANK-CE] Loading cross-encoder model: %s",
                self._settings.cross_encoder_model,
            )
            _cross_encoder_model = CrossEncoder(self._settings.cross_encoder_model)
            return _cross_encoder_model
        except Exception as exc:
            logger.error("[RERANK-CE] Failed to load model: %s", exc)
            return None

    @staticmethod
    def _normalize_batch(scores: np.ndarray) -> np.ndarray:
        """Min-max normalize raw logits to [0, 1] within the batch."""
        min_s = float(scores.min())
        max_s = float(scores.max())
        if max_s - min_s < 1e-6:
            return np.full_like(scores, 0.5)
        return (scores - min_s) / (max_s - min_s)
