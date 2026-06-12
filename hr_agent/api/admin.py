"""
Admin routes — data management helpers (not for production use).

DELETE /admin/clear-all   — wipe all data from every table
GET    /admin/jobs        — list every job in the DB
GET    /admin/candidates  — list every candidate in the DB
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from hr_agent.api.deps import get_db
from hr_agent.models.candidate import Candidate
from hr_agent.models.embedding import Embedding
from hr_agent.models.job import Job
from hr_agent.models.match_result import MatchResult
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.schemas.candidate import CandidateResponse
from hr_agent.schemas.job import JobResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _job_status(job: Job, db: Session) -> str:
    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=job.id, entity_type="job")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    return log.status if log else ProcessingStatus.PENDING


def _candidate_status(candidate: Candidate, db: Session) -> str:
    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=candidate.id, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    return log.status if log else ProcessingStatus.PENDING


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.delete("/clear-all")
def clear_all_data(db: Session = Depends(get_db)):
    """Delete every record from every table. Use before a fresh test run."""
    counts = {}
    for model, name in [
        (MatchResult, "match_results"),
        (Embedding, "embeddings"),
        (ProcessingLog, "processing_logs"),
        (Candidate, "candidates"),
        (Job, "jobs"),
    ]:
        counts[name] = db.query(model).delete()
    db.commit()
    logger.warning("[ADMIN] clear-all executed — deleted: %s", counts)
    return {"cleared": True, "counts": counts}


@router.get("/jobs", response_model=list[JobResponse])
def list_all_jobs(db: Session = Depends(get_db)):
    """Return every job in the DB with its current processing status."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    results = []
    for job in jobs:
        status = _job_status(job, db)
        results.append(
            JobResponse(
                id=job.id,
                title=job.title,
                normalized_role=job.normalized_role,
                experience_min=job.experience_min,
                experience_max=job.experience_max,
                employment_type=job.employment_type,
                location=job.location,
                must_have_skills=job.must_have_skills or [],
                good_to_have_skills=job.good_to_have_skills or [],
                education_requirements=job.education_requirements or [],
                certifications=job.certifications or [],
                responsibilities=job.responsibilities or [],
                tools_and_technologies=job.tools_and_technologies or [],
                seniority_level=job.seniority_level,
                department=job.department,
                industry=job.industry,
                summary=job.summary,
                hard_checks=job.hard_checks,
                status=status,
                created_at=job.created_at,
            )
        )
    return results


@router.get("/candidates", response_model=list[CandidateResponse])
def list_all_candidates(db: Session = Depends(get_db)):
    """Return every candidate in the DB with its current processing status."""
    candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    results = []
    for c in candidates:
        status = _candidate_status(c, db)
        results.append(
            CandidateResponse(
                id=c.id,
                name=c.name,
                current_title=c.current_title,
                normalized_role=c.normalized_role,
                years_experience=c.years_experience,
                current_company=c.current_company,
                location=c.location,
                skills=c.skills or [],
                tools_and_technologies=c.tools_and_technologies or [],
                education=c.education or [],
                certifications=c.certifications or [],
                employment_history=c.employment_history or [],
                industries=c.industries or [],
                experience_areas=c.experience_areas or [],
                responsibilities=c.responsibilities or [],
                seniority_level=c.seniority_level,
                summary=c.summary,
                status=status,
                created_at=c.created_at,
            )
        )
    return results
