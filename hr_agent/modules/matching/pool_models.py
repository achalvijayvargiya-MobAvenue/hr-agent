import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.core.database import Base


class JobCandidatePool(Base):
    """Per-job candidate pool — domain/subdomain grouping (Phase 2)."""

    __tablename__ = "job_candidate_pools"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_job_pool_candidate"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidates.email"), nullable=False)

    pool_status: Mapped[str] = mapped_column(String, nullable=False, default="out_of_pool")
    domain_match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subdomain_match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<JobCandidatePool job={self.job_id!r} candidate={self.candidate_id!r} "
            f"status={self.pool_status} relevance={self.relevance_score}>"
        )
