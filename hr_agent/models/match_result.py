import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidates.id"), nullable=False)

    # Hard-filter outcome
    is_filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Individual stage scores (None until that stage has run)
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<MatchResult job={self.job_id!r} candidate={self.candidate_id!r} "
            f"final={self.final_score}>"
        )
