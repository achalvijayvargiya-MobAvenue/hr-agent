from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ZohoCandidate(Base):
    """Local mirror of a Zoho Recruit candidate record."""

    __tablename__ = "zoho_candidates"

    zoho_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    modified_time: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_downloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resume_attachment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    local_candidate_email: Mapped[str | None] = mapped_column(
        String, ForeignKey("candidates.email"), nullable=True
    )
    sync_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ZohoCandidate zoho_id={self.zoho_id!r} sync_status={self.sync_status!r}>"
