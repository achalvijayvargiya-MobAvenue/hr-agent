"""
Embedding service.

Generates text embeddings via OpenAI and stores them as numpy BLOB columns
in SQLite. Cosine similarity is computed in Python with numpy at query time.
"""
import io
import logging

import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.embedding import Embedding

logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self, settings: Settings, client: OpenAI) -> None:
        self._settings = settings
        self._client = client
        logger.debug(
            "[EMBED] EmbeddingService initialised — model: %s",
            settings.embedding_model,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def generate_and_store(
        self,
        db: Session,
        entity_type: str,
        entity_id: str,
        text: str,
    ) -> Embedding:
        """Generate an embedding for `text` and persist it (idempotent)."""
        logger.info(
            "[EMBED] Generating embedding — entity: %s/%s  text_length: %d chars  model: %s",
            entity_type, entity_id, len(text), self._settings.embedding_model,
        )

        vector = self._embed(text)
        blob = self._serialize(vector)
        model_name = self._settings.embedding_model

        existing = (
            db.query(Embedding)
            .filter_by(entity_type=entity_type, entity_id=entity_id, model_name=model_name)
            .first()
        )

        if existing:
            existing.vector_blob = blob
            db.commit()
            db.refresh(existing)
            logger.info(
                "[EMBED] Updated existing embedding — entity: %s/%s  dims: %d",
                entity_type, entity_id, len(vector),
            )
            return existing

        embedding = Embedding(
            entity_type=entity_type,
            entity_id=entity_id,
            model_name=model_name,
            vector_blob=blob,
        )
        db.add(embedding)
        db.commit()
        db.refresh(embedding)
        logger.info(
            "[EMBED] Stored new embedding — entity: %s/%s  dims: %d  blob_size: %d bytes",
            entity_type, entity_id, len(vector), len(blob),
        )
        return embedding

    def load_vector(self, db: Session, entity_type: str, entity_id: str) -> np.ndarray | None:
        """Load and deserialise the stored embedding vector, or None if not found."""
        row = (
            db.query(Embedding)
            .filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                model_name=self._settings.embedding_model,
            )
            .first()
        )
        if row is None:
            logger.warning(
                "[EMBED] No embedding found for %s/%s (model: %s).",
                entity_type, entity_id, self._settings.embedding_model,
            )
            return None

        vector = self._deserialize(row.vector_blob)
        logger.debug(
            "[EMBED] Loaded embedding — entity: %s/%s  dims: %d",
            entity_type, entity_id, len(vector),
        )
        return vector

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Return cosine similarity in [0, 1] between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            logger.warning("[EMBED] Zero-norm vector encountered in cosine similarity — returning 0.")
            return 0.0
        score = float(np.dot(a, b) / (norm_a * norm_b))
        return score

    # ── Private helpers ───────────────────────────────────────────────────────

    def _embed(self, text: str) -> np.ndarray:
        response = self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=text,
        )
        usage = response.usage
        if usage:
            logger.info(
                "[EMBED] Embedding API usage — prompt_tokens: %d  total_tokens: %d",
                usage.prompt_tokens, usage.total_tokens,
            )
        return np.array(response.data[0].embedding, dtype=np.float32)

    @staticmethod
    def _serialize(vector: np.ndarray) -> bytes:
        buf = io.BytesIO()
        np.save(buf, vector)
        return buf.getvalue()

    @staticmethod
    def _deserialize(blob: bytes) -> np.ndarray:
        return np.load(io.BytesIO(blob))
