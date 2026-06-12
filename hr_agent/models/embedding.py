"""
Stores serialised numpy float32 embedding vectors as BLOBs.
One row per (entity_type, entity_id, model_name) combination so embeddings
can be re-generated when the model changes without losing older ones.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String, nullable=False)   # "job" | "candidate"
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    vector_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Embedding entity_type={self.entity_type!r} entity_id={self.entity_id!r}>"
