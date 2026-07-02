"""
Structured profile fingerprints for bi-encoder retrieval (Phase 4).

Embeds explicit fields (role, domain, skills, seniority, etc.) instead of
summary-only text for more reliable semantic matching.
"""
from __future__ import annotations

from hr_agent.models.candidate import Candidate
from hr_agent.models.job import Job


def _join(items: list[str] | None, limit: int = 12) -> str:
    if not items:
        return "none"
    return ", ".join(items[:limit])


def build_job_fingerprint(job: Job) -> str:
    """Compact structured text representing a job for embedding / cross-encoder."""
    domain = job.domain_code or "unspecified"
    subdomains = ", ".join(job.subdomain_codes or []) or "unspecified"
    exp = (
        f"{job.experience_min or '?'}–{job.experience_max or '?'}"
        if job.experience_min is not None or job.experience_max is not None
        else "unspecified"
    )
    lines = [
        f"Role: {job.normalized_role or job.title or 'unknown'}",
        f"Domain: {domain} | Subdomains: {subdomains}",
        f"Seniority: {job.seniority_level or 'unspecified'} | Experience: {exp} years",
        f"Must-have skills: {_join(job.must_have_skills)}",
        f"Good-to-have skills: {_join(job.good_to_have_skills)}",
        f"Tools: {_join(job.tools_and_technologies)}",
        f"Education: {_join(job.education_requirements, 5)}",
        f"Certifications: {_join(job.certifications, 5)}",
        f"Industry: {job.industry or 'unspecified'} | Location: {job.location or 'unspecified'}",
        f"Responsibilities: {_join(job.responsibilities, 6)}",
    ]
    if job.summary:
        lines.append(f"Summary: {job.summary[:500]}")
    return "\n".join(lines)


def build_candidate_fingerprint(candidate: Candidate) -> str:
    """Compact structured text representing a candidate for embedding / cross-encoder."""
    domain = candidate.domain_code or "unspecified"
    subdomains = ", ".join(candidate.subdomain_codes or []) or "unspecified"
    skills = _join((candidate.skills or []) + (candidate.tools_and_technologies or []))

    education_parts = []
    for edu in (candidate.education or [])[:3]:
        if isinstance(edu, dict):
            education_parts.append(
                f"{edu.get('degree') or ''} {edu.get('institution') or ''}".strip()
            )
    education = "; ".join(education_parts) or "none"

    emp_parts = []
    for emp in (candidate.employment_history or [])[:3]:
        if isinstance(emp, dict):
            emp_parts.append(
                f"{emp.get('title', '?')} @ {emp.get('company', '?')}"
            )
    employment = "; ".join(emp_parts) or "none"

    lines = [
        f"Role: {candidate.normalized_role or candidate.current_title or 'unknown'}",
        f"Title: {candidate.current_title or 'unknown'} @ {candidate.current_company or 'unknown'}",
        f"Domain: {domain} | Subdomains: {subdomains}",
        f"Seniority: {candidate.seniority_level or 'unspecified'} | "
        f"Experience: {candidate.years_experience if candidate.years_experience is not None else 'unknown'} years",
        f"Skills & tools: {skills}",
        f"Certifications: {_join(candidate.certifications, 5)}",
        f"Experience areas: {_join(candidate.experience_areas, 6)}",
        f"Industries: {_join(candidate.industries, 5)}",
        f"Education: {education}",
        f"Employment: {employment}",
        f"Responsibilities: {_join(candidate.responsibilities, 5)}",
    ]
    if candidate.summary:
        lines.append(f"Summary: {candidate.summary[:500]}")
    return "\n".join(lines)
