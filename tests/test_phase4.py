"""Tests for Phase 4 fingerprint retrieval and cross-encoder rerank."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hr_agent.modules.matching.cross_encoder_service import CrossEncoderService
from hr_agent.modules.matching.profile_fingerprint_service import (
    build_candidate_fingerprint,
    build_job_fingerprint,
)


def _job(**kwargs):
    defaults = dict(
        id="job-1",
        title="Backend Engineer",
        normalized_role="backend_engineer",
        domain_code="TECH",
        subdomain_codes=["TECH.SWE.BACKEND"],
        seniority_level="mid",
        experience_min=3,
        experience_max=7,
        must_have_skills=["Python", "FastAPI"],
        good_to_have_skills=["PostgreSQL"],
        tools_and_technologies=["Docker"],
        education_requirements=["B.Tech"],
        certifications=[],
        industry="SaaS",
        location="Remote",
        responsibilities=["Build APIs"],
        summary="Backend role building REST APIs.",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _candidate(**kwargs):
    defaults = dict(
        email="dev@example.com",
        name="Dev User",
        current_title="Software Engineer",
        current_company="Acme",
        normalized_role="backend_engineer",
        domain_code="TECH",
        subdomain_codes=["TECH.SWE.BACKEND"],
        seniority_level="mid",
        years_experience=5,
        skills=["Python", "FastAPI"],
        tools_and_technologies=["Docker"],
        certifications=[],
        experience_areas=["API development"],
        industries=["SaaS"],
        education=[{"degree": "B.Tech", "institution": "IIT"}],
        employment_history=[{"title": "Software Engineer", "company": "Acme"}],
        responsibilities=["Built REST APIs"],
        summary="Backend developer with Python experience.",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── Fingerprint builder ───────────────────────────────────────────────────────

def test_job_fingerprint_includes_role_and_skills():
    fp = build_job_fingerprint(_job())
    assert "Role: backend_engineer" in fp
    assert "Must-have skills: Python, FastAPI" in fp
    assert "Domain: TECH" in fp


def test_candidate_fingerprint_includes_education_and_employment():
    fp = build_candidate_fingerprint(_candidate())
    assert "Skills & tools: Python, FastAPI, Docker" in fp
    assert "B.Tech IIT" in fp
    assert "Software Engineer @ Acme" in fp


def test_fingerprint_handles_empty_fields():
    fp = build_job_fingerprint(_job(must_have_skills=None, summary=None))
    assert "Must-have skills: none" in fp
    assert "Summary:" not in fp


# ── Cross-encoder service ─────────────────────────────────────────────────────

def test_cross_encoder_disabled_returns_neutral():
    settings = SimpleNamespace(cross_encoder_enabled=False, cross_encoder_model="test")
    svc = CrossEncoderService(settings)
    scores = svc.score_pairs("query", ["doc1", "doc2"])
    assert scores == [0.5, 0.5]


def test_cross_encoder_empty_documents():
    settings = SimpleNamespace(cross_encoder_enabled=True, cross_encoder_model="test")
    svc = CrossEncoderService(settings)
    assert svc.score_pairs("query", []) == []


@patch("hr_agent.modules.matching.cross_encoder_service._cross_encoder_model", None)
def test_cross_encoder_normalizes_batch():
    settings = SimpleNamespace(
        cross_encoder_enabled=True,
        cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    svc = CrossEncoderService(settings)

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([1.0, 3.0, 2.0])

    with patch.object(svc, "_load_model", return_value=mock_model):
        scores = svc.score_pairs("job fp", ["cand1", "cand2", "cand3"])

    assert scores == [0.0, 1.0, 0.5]
    mock_model.predict.assert_called_once()


@patch("hr_agent.modules.matching.cross_encoder_service._cross_encoder_model", None)
def test_cross_encoder_identical_scores_return_neutral():
    settings = SimpleNamespace(
        cross_encoder_enabled=True,
        cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    svc = CrossEncoderService(settings)

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([2.0, 2.0])

    with patch.object(svc, "_load_model", return_value=mock_model):
        scores = svc.score_pairs("job fp", ["cand1", "cand2"])

    assert scores == [0.5, 0.5]


def test_phase4_final_score_blend():
    """Sanity check for the 25/25/50 weight formula."""
    fit, retrieval, rerank = 0.8, 0.6, 0.9
    final = 0.25 * fit + 0.25 * retrieval + 0.50 * rerank
    assert final == pytest.approx(0.8)
