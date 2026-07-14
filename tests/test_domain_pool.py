"""Tests for taxonomy and pool scoring (Phase 1–2)."""
from hr_agent.modules.taxonomy import taxonomy_service
from hr_agent.modules.matching.pool_service import compute_relevance_score, compute_subdomain_match_score


def test_taxonomy_loads():
    assert taxonomy_service.taxonomy_version() == "2026.07"
    assert "TECH" in taxonomy_service.domain_codes()
    assert "MEDIA.PROGRAMMATIC" in taxonomy_service.subdomain_codes()


def test_exact_subdomain_match():
    score, reason = compute_subdomain_match_score(
        {"TECH.SWE.BACKEND"}, {"TECH.SWE.BACKEND"}
    )
    assert score == 1.0
    assert "exact subdomain" in reason


def test_adjacent_subdomain_match():
    score, reason = compute_subdomain_match_score(
        {"TECH.SWE.BACKEND"}, {"TECH.SWE.FULLSTACK"}
    )
    assert score == 0.75
    assert "adjacent" in reason


def test_same_domain_different_subdomain():
    score, _ = compute_subdomain_match_score(
        {"TECH.SWE.BACKEND"}, {"TECH.DATA.SCIENCE"}
    )
    assert score == 0.45


def test_relevance_score_formula():
    assert compute_relevance_score(1.0, 1.0) == 1.0
    assert compute_relevance_score(1.0, 0.45) == 0.6425


def test_media_programmatic_in_taxonomy():
    media = taxonomy_service.get_domain("MEDIA")
    assert media is not None
    codes = {s["code"] for s in media["subdomains"]}
    assert "MEDIA.PROGRAMMATIC" in codes
    assert "MEDIA.DSP" in codes
