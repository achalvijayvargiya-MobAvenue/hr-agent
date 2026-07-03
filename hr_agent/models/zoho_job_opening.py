from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ZohoJobOpening(Base):
    """Local mirror of a Zoho Recruit job opening."""

    __tablename__ = "zoho_job_openings"

    zoho_id: Mapped[str] = mapped_column(String, primary_key=True)
    posting_title: Mapped[str | None] = mapped_column(String, nullable=True)
    modified_time: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mapped_job_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("jobs.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ZohoJobOpening zoho_id={self.zoho_id!r} title={self.posting_title!r}>"
