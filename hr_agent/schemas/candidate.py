"""
Pydantic schemas for Candidate entities.

CVExtracted       — exact JSON structure GPT-4o must return (mirrors cv_extraction.txt prompt).
CandidateResponse — what the API returns to callers.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class EducationEntry(BaseModel):
    degree: str | None = None
    institution: str | None = None
    year: int | None = None


class EmploymentHistoryEntry(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CVExtracted(BaseModel):
    """
    Mirrors the schema section in hr_agent/prompts/cv_extraction.txt exactly.
    Every field added to the prompt must be added here so Pydantic validates it.
    """

    candidate_name: str
    current_title: str | None = None
    normalized_role: str
    years_experience: float | None = None
    current_company: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    employment_history: list[EmploymentHistoryEntry] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    experience_areas: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    summary: str


class CandidateResponse(BaseModel):
    """API response shape for a Candidate resource — includes all extracted fields."""

    id: str
    name: str | None
    current_title: str | None
    normalized_role: str | None
    years_experience: float | None
    current_company: str | None
    location: str | None
    skills: list[str]
    tools_and_technologies: list[str]
    education: list[dict]
    certifications: list[str]
    employment_history: list[dict]
    industries: list[str]
    experience_areas: list[str]
    responsibilities: list[str]
    seniority_level: str | None
    summary: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateUploadResponse(BaseModel):
    candidate_id: str
    status: str
    message: str
