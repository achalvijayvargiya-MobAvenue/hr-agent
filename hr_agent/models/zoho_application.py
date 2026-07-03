from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ZohoApplication(Base):
    """Local mirror of a Zoho Recruit application linking candidate to job opening."""

    __tablename__ = "zoho_applications"

    zoho_id: Mapped[str] = mapped_column(String, primary_key=True)
    zoho_candidate_id: Mapped[str] = mapped_column(
        String, ForeignKey("zoho_candidates.zoho_id"), nullable=False, index=True
    )
    zoho_job_opening_id: Mapped[str] = mapped_column(
        String, ForeignKey("zoho_job_openings.zoho_id"), nullable=False, index=True
    )
    application_status: Mapped[str | None] = mapped_column(String, nullable=True)
    modified_time: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ZohoApplication zoho_id={self.zoho_id!r} status={self.application_status!r}>"
