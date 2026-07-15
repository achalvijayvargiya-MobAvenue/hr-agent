"""
Build and manage per-job candidate pools based on domain/subdomain taxonomy.

Phase 2: grouping only — no requirement filters or ranking here.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from hr_agent.core.config import Settings
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.matching.pool_models import JobCandidatePool
import hr_agent.modules.taxonomy.taxonomy_service as taxonomy_service

logger = logging.getLogger(__name__)

# Minimum relevance to auto-include in pool (same domain + weak subdomain overlap)
DEFAULT_MIN_RELEVANCE = 0.5

EXACT_SUBDOMAIN_SCORE = 1.0
ADJACENT_SUBDOMAIN_SCORE = 0.75
SAME_DOMAIN_ONLY_SCORE = 0.45


def compute_subdomain_match_score(job_subdomains: set[str], cand_subdomains: set[str]) -> tuple[float, str]:
    """Return (score, reason) for subdomain overlap between job and candidate."""
    if not job_subdomains or not cand_subdomains:
        return SAME_DOMAIN_ONLY_SCORE, "same domain — subdomain not specified on one side"

    overlap = job_subdomains & cand_subdomains
    if overlap:
        code = sorted(overlap)[0]
        label = taxonomy_service.get_subdomain(code)
        name = label["label"] if label else code
        return EXACT_SUBDOMAIN_SCORE, f"exact subdomain match: {name}"

    # Check adjacency from job subdomains to candidate subdomains
    for job_sub in job_subdomains:
        adjacent = taxonomy_service.adjacent_subdomains(job_sub)
        hit = adjacent & cand_subdomains
        if hit:
            code = sorted(hit)[0]
            label = taxonomy_service.get_subdomain(code)
            name = label["label"] if label else code
            return ADJACENT_SUBDOMAIN_SCORE, f"adjacent subdomain: {name}"

    # Reverse: candidate subdomain adjacent to job
    for cand_sub in cand_subdomains:
        adjacent = taxonomy_service.adjacent_subdomains(cand_sub)
        hit = adjacent & job_subdomains
        if hit:
            code = sorted(hit)[0]
            label = taxonomy_service.get_subdomain(code)
            name = label["label"] if label else code
            return ADJACENT_SUBDOMAIN_SCORE, f"adjacent subdomain: {name}"

    return SAME_DOMAIN_ONLY_SCORE, "same domain — different subdomain"


def compute_relevance_score(domain_match: float, subdomain_score: float) -> float:
    return round(0.35 * domain_match + 0.65 * subdomain_score, 4)


class PoolService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._min_relevance = DEFAULT_MIN_RELEVANCE

    def build_pool(self, db: Session, job_id: str) -> list[JobCandidatePool]:
        """
        Rebuild the candidate pool for a job from taxonomy rules.
        Preserves manual_add / manual_exclude overrides across rebuilds.
        """
        job = db.query(Job).filter_by(id=job_id).first()
        if job is None:
            raise ValueError(f"Job {job_id!r} not found.")
        if not job.domain_code:
            raise ValueError(
                f"Job {job_id!r} has no domain assigned. Classify or set domain before building pool."
            )

        logger.info(
            "[POOL] Building pool for job %s — domain=%s  subdomains=%s",
            job_id, job.domain_code, job.subdomain_codes,
        )

        manual: dict[str, str] = {
            row.candidate_id: row.pool_status
            for row in db.query(JobCandidatePool).filter_by(job_id=job_id).all()
            if row.pool_status in ("manual_add", "manual_exclude")
        }

        db.query(JobCandidatePool).filter_by(job_id=job_id).delete()

        candidates = db.query(Candidate).filter(Candidate.normalized_role.isnot(None)).all()
        now = datetime.now(timezone.utc)
        results: list[JobCandidatePool] = []

        for candidate in candidates:
            override = manual.get(candidate.email)
            if override == "manual_exclude":
                row = JobCandidatePool(
                    job_id=job.id,
                    candidate_id=candidate.email,
                    pool_status="manual_exclude",
                    domain_match_score=0.0,
                    subdomain_match_score=0.0,
                    relevance_score=0.0,
                    match_reason="manually excluded from pool",
                    computed_at=now,
                )
            elif override == "manual_add":
                row = self._score_candidate(job, candidate, now)
                row.pool_status = "manual_add"
                row.match_reason = (row.match_reason or "") + " (manual add)"
            else:
                row = self._score_candidate(job, candidate, now)

            db.add(row)
            results.append(row)

        db.commit()

        in_pool = sum(1 for r in results if r.pool_status in ("in_pool", "manual_add"))
        logger.info(
            "[POOL] Pool built — job=%s  total=%d  in_pool=%d  out=%d",
            job_id, len(results), in_pool, len(results) - in_pool,
        )
        return results

    def _score_candidate(self, job: Job, candidate: Candidate, now: datetime) -> JobCandidatePool:
        job_subs = set(job.subdomain_codes or [])
        cand_subs = set(candidate.subdomain_codes or [])

        if not candidate.domain_code:
            return JobCandidatePool(
                id=str(uuid.uuid4()),
                job_id=job.id,
                candidate_id=candidate.email,
                pool_status="out_of_pool",
                domain_match_score=0.0,
                subdomain_match_score=0.0,
                relevance_score=0.0,
                match_reason="candidate has no domain classification",
                computed_at=now,
            )

        if candidate.domain_code != job.domain_code:
            domain = taxonomy_service.get_domain(candidate.domain_code)
            name = domain["label"] if domain else candidate.domain_code
            return JobCandidatePool(
                id=str(uuid.uuid4()),
                job_id=job.id,
                candidate_id=candidate.email,
                pool_status="out_of_pool",
                domain_match_score=0.0,
                subdomain_match_score=0.0,
                relevance_score=0.0,
                match_reason=f"domain mismatch — candidate is {name}",
                computed_at=now,
            )

        sub_score, reason = compute_subdomain_match_score(job_subs, cand_subs)
        relevance = compute_relevance_score(1.0, sub_score)
        status = "in_pool" if relevance >= self._min_relevance else "out_of_pool"

        return JobCandidatePool(
            id=str(uuid.uuid4()),
            job_id=job.id,
            candidate_id=candidate.email,
            pool_status=status,
            domain_match_score=1.0,
            subdomain_match_score=sub_score,
            relevance_score=relevance,
            match_reason=reason,
            computed_at=now,
        )

    def set_member_status(
        self,
        db: Session,
        job_id: str,
        candidate_id: str,
        pool_status: str,
    ) -> JobCandidatePool:
        row = (
            db.query(JobCandidatePool)
            .filter_by(job_id=job_id, candidate_id=candidate_id)
            .first()
        )
        if row is None:
            raise ValueError(f"Pool entry not found for job={job_id} candidate={candidate_id}")

        if pool_status == "auto":
            # Re-score this candidate
            job = db.query(Job).filter_by(id=job_id).first()
            candidate = db.query(Candidate).filter_by(email=candidate_id).first()
            if job and candidate:
                now = datetime.now(timezone.utc)
                updated = self._score_candidate(job, candidate, now)
                updated.id = row.id
                db.merge(updated)
                db.commit()
                db.refresh(updated)
                return updated
            pool_status = "in_pool"

        row.pool_status = pool_status  # type: ignore[assignment]
        row.computed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def sync_candidate_across_pools(self, db: Session, candidate_id: str) -> None:
        """
        Re-score a candidate in all existing job pools (e.g. after a domain update).
        Preserves manual_add / manual_exclude overrides.
        """
        candidate = db.query(Candidate).filter_by(email=candidate_id).first()
        if not candidate:
            return

        pools = db.query(JobCandidatePool).filter_by(candidate_id=candidate_id).all()
        if not pools:
            return

        now = datetime.now(timezone.utc)
        updated_count = 0
        for row in pools:
            if row.pool_status in ("manual_add", "manual_exclude"):
                continue

            job = db.query(Job).filter_by(id=row.job_id).first()
            if not job:
                continue

            updated = self._score_candidate(job, candidate, now)
            row.pool_status = updated.pool_status
            row.domain_match_score = updated.domain_match_score
            row.subdomain_match_score = updated.subdomain_match_score
            row.relevance_score = updated.relevance_score
            row.match_reason = updated.match_reason
            row.computed_at = updated.computed_at
            updated_count += 1
            
        if updated_count > 0:
            db.commit()
            logger.info("[POOL] Synced candidate %s across %d pools", candidate_id, updated_count)

    def get_pool(self, db: Session, job_id: str) -> list[JobCandidatePool]:
        return (
            db.query(JobCandidatePool)
            .filter_by(job_id=job_id)
            .order_by(JobCandidatePool.relevance_score.desc())
            .all()
        )
