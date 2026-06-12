import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Core fields (original)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_role: Mapped[str | None] = mapped_column(String, nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    education: Mapped[list | None] = mapped_column(JSON, nullable=True)
    industries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New fields from updated cv_extraction.txt prompt
    current_title: Mapped[str | None] = mapped_column(String, nullable=True)
    current_company: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    tools_and_technologies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)
    employment_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    experience_areas: Mapped[list | None] = mapped_column(JSON, nullable=True)
    responsibilities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id!r} name={self.name!r}>"
