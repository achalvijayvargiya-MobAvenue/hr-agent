import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.core.database import Base


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_app_job_candidate"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidates.email"), nullable=False)
    
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    zoho_application_id: Mapped[str | None] = mapped_column(String, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<JobApplication job={self.job_id!r} candidate={self.candidate_id!r} status={self.status!r}>"
