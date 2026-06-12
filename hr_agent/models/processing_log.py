import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"     # PDF text extracted
    STRUCTURED = "STRUCTURED"   # LLM extraction complete
    EMBEDDED = "EMBEDDED"       # Embedding stored
    FAILED = "FAILED"


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String, nullable=False)  # "job" | "candidate"
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=ProcessingStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProcessingLog entity={self.entity_type}/{self.entity_id} status={self.status!r}>"
