"""Tests for GitHub search query builder."""
from hr_agent.models.job import Job
from hr_agent.services.candidate_sources.github_query import (
    build_github_search_query,
    plan_github_search,
)


def test_tech_job_builds_effective_query():
    job = Job(
        title="Senior Backend Engineer",
        normalized_role="backend engineer",
        must_have_skills=["Python", "FastAPI", "PostgreSQL"],
        good_to_have_skills=["Docker"],
        tools_and_technologies=["AWS"],
        location="Mumbai, India",
        experience_min=5,
    )
    plan = plan_github_search(job)

    assert plan.suitable is True
    assert plan.languages == ["python"]
    assert "fastapi" in plan.dev_keywords
    assert "postgresql" in plan.dev_keywords
    assert plan.query is not None
    assert "backend engineer" in plan.query
    assert "language:python" in plan.query
    assert "fastapi" in plan.query
    assert 'location:"Mumbai, India"' in plan.query
    assert "repos:>8" in plan.query
    assert "type:user" in plan.query
    assert len(plan.query) <= 256


def test_non_tech_job_skips_github_search():
    job = Job(
        title="Company Secretary",
        normalized_role="company secretary",
        must_have_skills=[
            "corporate governance",
            "legal compliance",
            "IPO drafting",
        ],
        location="Mumbai",
        experience_min=8,
    )
    plan = plan_github_search(job)

    assert plan.suitable is False
    assert plan.query is None
    assert "corporate governance" in plan.skipped_skills
    assert build_github_search_query(job) is None


def test_devops_role_without_language_still_suitable():
    job = Job(
        normalized_role="devops engineer",
        tools_and_technologies=["Kubernetes", "Terraform", "AWS"],
        location="Pune",
        experience_min=3,
    )
    plan = plan_github_search(job)

    assert plan.suitable is True
    assert plan.query is not None
    assert "kubernetes" in plan.query
    assert "repos:>3" in plan.query
