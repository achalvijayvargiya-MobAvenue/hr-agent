"""
Pydantic schemas for Job entities.

JDExtracted     — exact JSON structure GPT-4o must return (mirrors jd_extraction.txt prompt).
JobResponse     — what the API returns to callers.
HardChecksUpdate — request body for PUT /jobs/{id}/hard-checks.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JDExtracted(BaseModel):
    """
    Mirrors the schema section in hr_agent/prompts/jd_extraction.txt exactly.
    Every field added to the prompt must be added here so Pydantic validates it.
    """

    title: str
    normalized_role: str
    experience_min: int | None = None
    experience_max: int | None = None
    employment_type: str | None = None
    location: str | None = None
    department: str | None = None
    industry: str | None = None
    must_have_skills: list[str] = Field(default_factory=list)
    good_to_have_skills: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    summary: str


class JobResponse(BaseModel):
    """API response shape for a Job resource — includes all extracted fields."""

    id: str
    title: str | None
    normalized_role: str | None
    experience_min: int | None
    experience_max: int | None
    employment_type: str | None
    location: str | None
    department: str | None
    industry: str | None
    must_have_skills: list[str]
    good_to_have_skills: list[str]
    education_requirements: list[str]
    certifications: list[str]
    responsibilities: list[str]
    tools_and_technologies: list[str]
    seniority_level: str | None
    summary: str | None
    hard_checks: dict[str, Any] | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HardChecksUpdate(BaseModel):
    """
    Request body for PUT /jobs/{id}/hard-checks.

    Keys are field names from JDExtracted.  Values are:
      - list[str]  for list-based fields (must_have_skills, tools_and_technologies, certifications)
      - str        for scalar fields      (seniority_level, normalized_role, industry, location)

    Empty dict removes all hard checks from the job.
    """
    hard_checks: dict[str, Any] = Field(default_factory=dict)


class JobUploadResponse(BaseModel):
    job_id: str
    status: str
    message: str
