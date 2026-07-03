from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class SyncMetadata(Base):
    """Tracks incremental sync watermarks per Zoho entity type."""

    __tablename__ = "sync_metadata"

    entity_type: Mapped[str] = mapped_column(String, primary_key=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_modified_time: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="idle")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SyncMetadata entity_type={self.entity_type!r} status={self.status!r}>"
