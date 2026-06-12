import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Core fields (original)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_role: Mapped[str | None] = mapped_column(String, nullable=True)
    experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    must_have_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    good_to_have_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New fields from updated jd_extraction.txt prompt
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    education_requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)
    responsibilities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tools_and_technologies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String, nullable=True)

    # User-configured hard checks: {field: [required values] | "required value"}
    hard_checks: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id!r} title={self.title!r}>"
