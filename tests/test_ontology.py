"""Tests for ontology-based requirement matching (Phase 3)."""
from types import SimpleNamespace

import pytest

from hr_agent.modules.taxonomy import ontology_service
from hr_agent.modules.matching.service import ontology_skill_score, passes_hard_filter
from hr_agent.modules.matching.requirement_fit_service import evaluate_requirement_fit


# ── Education ontology ────────────────────────────────────────────────────────

def test_llb_matches_l_dot_l_dot_b():
    assert ontology_service.education_requirement_satisfied(
        "LLB",
        [{"degree": "L.L.B.", "institution": "Delhi University"}],
    )


def test_llb_matches_bachelor_of_laws():
    assert ontology_service.education_requirement_satisfied(
        "LLB",
        [{"degree": "Bachelor of Laws", "institution": "NLSIU"}],
    )


def test_llb_does_not_match_unrelated_degree():
    assert not ontology_service.education_requirement_satisfied(
        "LLB",
        [{"degree": "B.Tech Computer Science", "institution": "IIT"}],
    )


def test_education_resolve_ids():
    ids = ontology_service.resolve_education_ids("L.L.B. from National Law School")
    assert "llb" in ids


# ── Skill ontology ────────────────────────────────────────────────────────────

def test_nodejs_matches_node():
    assert ontology_service.skill_requirement_satisfied("Node.js", ["Node"])


def test_postgresql_matches_postgres():
    assert ontology_service.skill_requirement_satisfied("PostgreSQL", ["Postgres"])


def test_fastapi_partial_pool():
    score = ontology_service.list_coverage_score(["FastAPI", "Python"], ["Python"])
    assert score == pytest.approx(0.5)


def test_ontology_skill_score_full_coverage():
    score = ontology_skill_score(["Node", "Python"], ["Node.js", "Python"])
    assert score == 1.0


# ── Hard filter integration ───────────────────────────────────────────────────

def _job(**kwargs):
    defaults = dict(
        experience_min=None,
        experience_max=None,
        hard_checks=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _candidate(**kwargs):
    defaults = dict(
        years_experience=5,
        skills=[],
        tools_and_technologies=[],
        certifications=[],
        education=[],
        seniority_level=None,
        normalized_role=None,
        industries=[],
        location=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_hard_filter_llb_passes_with_l_dot_l_dot_b():
    passed, reason = passes_hard_filter(
        _candidate(education=[{"degree": "L.L.B.", "institution": "DU"}]),
        _job(hard_checks={"education_requirements": ["LLB"]}),
    )
    assert passed is True
    assert reason == ""


def test_hard_filter_llb_fails_without_law_degree():
    passed, reason = passes_hard_filter(
        _candidate(education=[{"degree": "MBA", "institution": "IIM"}]),
        _job(hard_checks={"education_requirements": ["LLB"]}),
    )
    assert passed is False
    assert "education" in reason.lower() or "llb" in reason.lower()


def test_requirement_fit_score_partial():
    fit = evaluate_requirement_fit(
        _candidate(skills=["Python"]),
        _job(hard_checks={"must_have_skills": ["Python", "FastAPI"]}),
    )
    assert fit.passed is False
    assert fit.score == pytest.approx(0.5)
    assert len(fit.gaps) == 1
