"""
Requirement fit evaluation — ontology-aware hard checks and fit scoring.

Phase 3: replaces literal string matching for skills, education, and certifications.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.taxonomy import ontology_service

logger = logging.getLogger(__name__)


@dataclass
class RequirementFitResult:
    passed: bool
    score: float
    gaps: list[str] = field(default_factory=list)
    filter_reason: str = ""


def evaluate_requirement_fit(candidate: Candidate, job: Job) -> RequirementFitResult:
    """
    Evaluate all requirement checks for a candidate against a job.

    Always checks experience band. Applies hard_checks via ontology when configured.
    Returns a 0–1 fit score (1.0 = all requirements met).
    """
    gaps: list[str] = []
    checks_run = 0
    checks_passed = 0

    # ── Experience band (always) ──────────────────────────────────────────────
    years = candidate.years_experience
    if job.experience_min is not None and years is not None and years < job.experience_min:
        reason = f"experience {years}yr is below minimum {job.experience_min}yr"
        return RequirementFitResult(passed=False, score=0.0, gaps=[reason], filter_reason=reason)
    if job.experience_max is not None and years is not None and years > job.experience_max:
        reason = f"experience {years}yr exceeds maximum {job.experience_max}yr"
        return RequirementFitResult(passed=False, score=0.0, gaps=[reason], filter_reason=reason)

    hard_checks: dict = job.hard_checks or {}
    if not hard_checks:
        return RequirementFitResult(passed=True, score=1.0)

    cand_skill_pool = (candidate.skills or []) + (candidate.tools_and_technologies or [])
    cand_tools = candidate.tools_and_technologies or []
    cand_certs = candidate.certifications or []

    for field_name, required in hard_checks.items():
        if not required:
            continue

        items = required if isinstance(required, list) else [required]

        if field_name == "education_requirements":
            for item in items:
                checks_run += 1
                if ontology_service.education_requirement_satisfied(str(item), candidate.education):
                    checks_passed += 1
                else:
                    gaps.append(f"missing education: '{item}'")

        elif field_name == "must_have_skills":
            for item in items:
                checks_run += 1
                if ontology_service.skill_requirement_satisfied(str(item), cand_skill_pool):
                    checks_passed += 1
                else:
                    gaps.append(f"missing skill: '{item}'")

        elif field_name == "tools_and_technologies":
            for item in items:
                checks_run += 1
                if ontology_service.skill_requirement_satisfied(str(item), cand_tools):
                    checks_passed += 1
                else:
                    gaps.append(f"missing tool: '{item}'")

        elif field_name == "certifications":
            for item in items:
                checks_run += 1
                if ontology_service.skill_requirement_satisfied(str(item), cand_certs):
                    checks_passed += 1
                else:
                    gaps.append(f"missing certification: '{item}'")

        elif field_name == "seniority_level":
            checks_run += 1
            cand_val = (candidate.seniority_level or "").lower().strip()
            req_val = str(required).lower().strip()
            if not cand_val or not req_val or cand_val == req_val:
                checks_passed += 1
            else:
                gaps.append(f"seniority mismatch: required '{required}', candidate has '{candidate.seniority_level}'")

        elif field_name == "normalized_role":
            checks_run += 1
            from hr_agent.modules.matching.service import role_match_score

            cand_val = (candidate.normalized_role or "").strip()
            req_val = str(required).strip()
            if not cand_val or not req_val or role_match_score(cand_val, req_val) >= 0.35:
                checks_passed += 1
            else:
                gaps.append(
                    f"role mismatch: required '{required}', candidate has '{candidate.normalized_role}'"
                )

        elif field_name == "industry":
            checks_run += 1
            req_val = str(required).lower().strip()
            cand_industries = {i.lower().strip() for i in (candidate.industries or [])}
            if not req_val or req_val in cand_industries:
                checks_passed += 1
            else:
                gaps.append(
                    f"industry mismatch: required '{required}', candidate has {sorted(candidate.industries or [])}"
                )

        elif field_name == "location":
            checks_run += 1
            cand_val = (candidate.location or "").lower().strip()
            req_val = str(required).lower().strip()
            if not cand_val or not req_val or req_val in cand_val or cand_val in req_val:
                checks_passed += 1
            else:
                gaps.append(
                    f"location mismatch: required '{required}', candidate has '{candidate.location}'"
                )

    score = round(checks_passed / checks_run, 4) if checks_run else 1.0
    passed = len(gaps) == 0
    filter_reason = gaps[0] if gaps else ""

    return RequirementFitResult(
        passed=passed,
        score=score,
        gaps=gaps,
        filter_reason=filter_reason,
    )
