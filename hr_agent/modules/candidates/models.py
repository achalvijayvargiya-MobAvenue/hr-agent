from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.core.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    email: Mapped[str] = mapped_column(String, primary_key=True)

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
    switch_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Domain taxonomy (Phase 1)
    domain_code: Mapped[str | None] = mapped_column(String, nullable=True)
    domain_label: Mapped[str | None] = mapped_column(String, nullable=True)
    subdomain_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    subdomain_labels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    domain_confidence: Mapped[float | None] = mapped_column(nullable=True)
    domain_source: Mapped[str | None] = mapped_column(String, nullable=True)  # auto | manual
    domain_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)

    source_name: Mapped[str] = mapped_column(String, nullable=False, default="local_kb")
    source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_pdf: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    @property
    def has_cv(self) -> bool:
        return self.cv_pdf is not None

    def __repr__(self) -> str:
        return f"<Candidate email={self.email!r} name={self.name!r}>"
