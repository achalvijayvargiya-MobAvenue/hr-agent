"""Helpers for serializing domain fields on jobs and candidates."""

from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.jobs.models import Job


def job_domain_dict(job: Job) -> dict:
    return {
        "domain_code": job.domain_code,
        "domain_label": job.domain_label,
        "subdomain_codes": job.subdomain_codes or [],
        "subdomain_labels": job.subdomain_labels or [],
        "domain_confidence": job.domain_confidence,
        "domain_source": job.domain_source,
        "domain_evidence": job.domain_evidence or [],
    }


def candidate_domain_dict(candidate: Candidate) -> dict:
    return {
        "domain_code": candidate.domain_code,
        "domain_label": candidate.domain_label,
        "subdomain_codes": candidate.subdomain_codes or [],
        "subdomain_labels": candidate.subdomain_labels or [],
        "domain_confidence": candidate.domain_confidence,
        "domain_source": candidate.domain_source,
        "domain_evidence": candidate.domain_evidence or [],
    }
