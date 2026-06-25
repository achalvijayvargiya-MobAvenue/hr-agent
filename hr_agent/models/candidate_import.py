import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ImportStatus(StrEnum):
    PROCESSING = "PROCESSING"
    CONFLICT = "CONFLICT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DISCARDED = "DISCARDED"


class CandidateImport(Base):
    """Staging record for in-flight CV ingestion and duplicate-email conflicts."""

    __tablename__ = "candidate_imports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False, default="local_kb")
    status: Mapped[str] = mapped_column(String, nullable=False, default=ImportStatus.PROCESSING)

    proposed_email: Mapped[str | None] = mapped_column(String, nullable=True)
    existing_email: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    name: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<CandidateImport id={self.id!r} status={self.status!r} email={self.proposed_email!r}>"
