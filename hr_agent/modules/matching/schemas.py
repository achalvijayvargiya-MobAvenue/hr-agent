"""Pydantic schemas for matching and ranking responses."""
from datetime import datetime

from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    """Structured breakdown of how the final score was computed."""

    rule_score: float | None
    vector_score: float | None
    rerank_score: float | None = None
    llm_score: float | None
    final_score: float | None
    requirement_fit_score: float | None = None
    rule_weight: float
    vector_weight: float
    rerank_weight: float | None = None
    requirement_fit_weight: float | None = None
    llm_weight: float
    summary: str


class MatchEntry(BaseModel):
    """A single candidate entry in a ranked match result."""

    rank: int | None
    candidate_id: str
    candidate_name: str | None
    is_filtered: bool
    filter_reason: str | None
    requirement_fit_score: float | None = None
    requirement_gaps: list[str] | None = None
    rule_score: float | None
    vector_score: float | None
    rerank_score: float | None = None
    llm_score: float | None
    final_score: float | None
    explanation: str | None
    source_name: str | None = None
    score_breakdown: ScoreBreakdown | None = None


class MatchResponse(BaseModel):
    """Full response returned by GET /matches/{job_id}."""

    job_id: str
    total_candidates: int
    passed_filter: int
    matches: list[MatchEntry]
    computed_at: datetime | None


class RecomputeResponse(BaseModel):
    job_id: str
    triggered: bool
    message: str


class RecomputeRequest(BaseModel):
    job_id: str
    source_filter: list[str] | None = None
    top_k: int | None = None


class LLMRankItem(BaseModel):
    """Shape of each item GPT-4o must return during reranking."""

    candidate_id: str
    score: int
    explanation: str
