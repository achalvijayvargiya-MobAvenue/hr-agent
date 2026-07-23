"""Pydantic schemas for domain classification and candidate pools."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SubdomainAssignment(BaseModel):
    code: str
    label: str
    is_primary: bool = False


class DomainClassification(BaseModel):
    """LLM output for domain/subdomain assignment."""

    reasoning: str
    domain_code: str
    domain_label: str
    subdomains: list[SubdomainAssignment] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class DomainUpdate(BaseModel):
    """Manual domain override from the UI."""

    domain_code: str
    subdomain_codes: list[str] = Field(default_factory=list)

    @field_validator("subdomain_codes")
    @classmethod
    def at_least_one_subdomain(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one subdomain code is required.")
        return v


class TaxonomySubdomainResponse(BaseModel):
    code: str
    label: str
    adjacent: list[str] = Field(default_factory=list)


class TaxonomyDomainResponse(BaseModel):
    code: str
    label: str
    description: str = ""
    subdomains: list[TaxonomySubdomainResponse]


class TaxonomyResponse(BaseModel):
    version: str
    domains: list[TaxonomyDomainResponse]


PoolStatus = Literal["in_pool", "out_of_pool", "manual_add", "manual_exclude"]


class PoolEntryResponse(BaseModel):
    candidate_id: str
    candidate_name: str | None
    current_title: str | None
    domain_code: str | None
    subdomain_codes: list[str]
    pool_status: PoolStatus
    domain_match_score: float
    subdomain_match_score: float
    relevance_score: float
    match_reason: str | None
    computed_at: datetime
    application_status: str | None = None


class PoolBuildResponse(BaseModel):
    job_id: str
    total_candidates: int
    in_pool: int
    out_of_pool: int
    manual_add: int
    manual_exclude: int
    computed_at: datetime
    entries: list[PoolEntryResponse]


class PoolMemberUpdate(BaseModel):
    pool_status: Literal["manual_add", "manual_exclude", "auto"]
