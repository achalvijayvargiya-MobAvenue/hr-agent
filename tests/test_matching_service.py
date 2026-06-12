"""
Unit tests for the pure scoring functions in the matching service.
No DB, no LLM calls — just arithmetic.
"""
from types import SimpleNamespace

import pytest

from hr_agent.services.matching_service import (
    experience_band_score,
    industry_match_score,
    jaccard_skill_score,
    passes_hard_filter,
    role_match_score,
)


# ── jaccard_skill_score ────────────────────────────────────────────────────────

def test_jaccard_perfect_match():
    assert jaccard_skill_score(["Python", "FastAPI"], ["Python", "FastAPI"]) == 1.0


def test_jaccard_partial_match():
    score = jaccard_skill_score(["Python"], ["Python", "FastAPI"])
    assert score == pytest.approx(0.5)


def test_jaccard_no_required_skills():
    assert jaccard_skill_score([], []) == 1.0


def test_jaccard_case_insensitive():
    assert jaccard_skill_score(["python", "fastapi"], ["Python", "FastAPI"]) == 1.0


def test_jaccard_no_overlap():
    assert jaccard_skill_score(["Java"], ["Python", "FastAPI"]) == 0.0


# ── experience_band_score ──────────────────────────────────────────────────────

def test_experience_inside_band():
    assert experience_band_score(5, 4, 7) == 1.0


def test_experience_at_boundaries():
    assert experience_band_score(4, 4, 7) == 1.0
    assert experience_band_score(7, 4, 7) == 1.0


def test_experience_below_min():
    score = experience_band_score(2, 4, 7)
    assert 0.0 < score < 1.0


def test_experience_above_max():
    score = experience_band_score(10, 4, 7)
    assert 0.0 < score < 1.0


def test_experience_unknown():
    assert experience_band_score(None, 4, 7) == 0.5


def test_experience_no_requirement():
    assert experience_band_score(10, None, None) == 1.0


# ── role_match_score ───────────────────────────────────────────────────────────

def test_role_exact_match():
    assert role_match_score("backend_engineer", "backend_engineer") == 1.0


def test_role_mismatch():
    assert role_match_score("frontend_engineer", "backend_engineer") == 0.0


def test_role_unknown():
    assert role_match_score(None, "backend_engineer") == 0.5


# ── industry_match_score ───────────────────────────────────────────────────────

def test_industry_match():
    assert industry_match_score(["Financial Services", "Banking"], "Financial Services") == 1.0


def test_industry_no_match():
    assert industry_match_score(["E-commerce"], "Financial Services") == 0.0


def test_industry_no_requirement():
    assert industry_match_score([], None) == 1.0


# ── passes_hard_filter ────────────────────────────────────────────────────────

def _make_job(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="JOB-001",
        normalized_role="backend_engineer",
        experience_min=4,
        experience_max=7,
        must_have_skills=["Python", "FastAPI"],
        industry="Financial Services",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_candidate(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id="CV-001",
        normalized_role="backend_engineer",
        years_experience=5,
        skills=["Python", "FastAPI", "PostgreSQL"],
        industries=["Financial Services"],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_hard_filter_pass():
    passed, reason = passes_hard_filter(_make_candidate(), _make_job())
    assert passed is True
    assert reason == ""


def test_hard_filter_experience_too_low():
    passed, reason = passes_hard_filter(_make_candidate(years_experience=2), _make_job())
    assert passed is False
    assert "below minimum" in reason


def test_hard_filter_experience_too_high():
    passed, reason = passes_hard_filter(_make_candidate(years_experience=9), _make_job())
    assert passed is False
    assert "exceeds maximum" in reason


def test_hard_filter_missing_skill():
    passed, reason = passes_hard_filter(
        _make_candidate(skills=["Python"]),  # missing FastAPI
        _make_job(),
    )
    assert passed is False
    assert "fastapi" in reason.lower()
