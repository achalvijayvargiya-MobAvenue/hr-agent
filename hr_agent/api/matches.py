"""
Matching routes.

GET  /matches/{job_id}  — return ranked candidates for a job (runs pipeline if no results exist)
POST /recompute-match   — force a fresh pipeline run for a job
"""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from hr_agent.api.deps import get_db, get_matching_service
from hr_agent.models.candidate import Candidate
from hr_agent.models.match_result import MatchResult
from hr_agent.schemas.match import MatchEntry, MatchResponse, RecomputeResponse
from hr_agent.services.matching_service import MatchingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["matches"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _build_match_response(job_id: str, results: list[MatchResult], db: Session) -> MatchResponse:
    cand_ids = [r.candidate_id for r in results]
    candidates = db.query(Candidate).filter(Candidate.id.in_(cand_ids)).all()
    name_map: dict[str, str | None] = {c.id: c.name for c in candidates}

    ranked = sorted(
        [r for r in results if not r.is_filtered and r.final_score is not None],
        key=lambda r: r.final_score,
        reverse=True,
    )

    entries: list[MatchEntry] = []
    rank = 1
    for result in ranked:
        entries.append(
            MatchEntry(
                rank=rank,
                candidate_id=result.candidate_id,
                candidate_name=name_map.get(result.candidate_id),
                is_filtered=False,
                filter_reason=None,
                rule_score=result.rule_score,
                vector_score=result.vector_score,
                llm_score=result.llm_score,
                final_score=result.final_score,
                explanation=result.explanation,
            )
        )
        rank += 1

    for result in results:
        if result.is_filtered:
            entries.append(
                MatchEntry(
                    rank=None,
                    candidate_id=result.candidate_id,
                    candidate_name=name_map.get(result.candidate_id),
                    is_filtered=True,
                    filter_reason=result.filter_reason,
                    rule_score=None,
                    vector_score=None,
                    llm_score=None,
                    final_score=None,
                    explanation=None,
                )
            )

    latest_at = max((r.computed_at for r in results), default=None)

    return MatchResponse(
        job_id=job_id,
        total_candidates=len(results),
        passed_filter=len(ranked),
        matches=entries,
        computed_at=latest_at,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/matches/{job_id}", response_model=MatchResponse)
def get_matches(
    job_id: str,
    db: Session = Depends(get_db),
    matching_svc: MatchingService = Depends(get_matching_service),
):
    """
    Return ranked candidates for the given job.
    If no match results exist yet, runs the full pipeline synchronously first.
    """
    existing = db.query(MatchResult).filter_by(job_id=job_id).all()
    if existing:
        return _build_match_response(job_id, existing, db)

    # No cached results — run now
    try:
        results = matching_svc.run(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Matching pipeline failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Matching pipeline error: {exc}") from exc

    return _build_match_response(job_id, results, db)


class RecomputeRequest(BaseModel):
    job_id: str


@router.post("/recompute-match", response_model=RecomputeResponse, status_code=202)
def recompute_match(
    body: RecomputeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    matching_svc: MatchingService = Depends(get_matching_service),
):
    """
    Trigger a fresh full-pipeline run for `job_id`.
    Returns immediately; the pipeline runs in the background.
    Call GET /matches/{job_id} after a few seconds to see updated results.
    """
    from hr_agent.models.job import Job  # avoid circular at module level

    job = db.query(Job).filter_by(id=body.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {body.job_id!r} not found.")

    def _run_in_background(job_id: str) -> None:
        from hr_agent.database import SessionLocal

        bg_db = SessionLocal()
        try:
            matching_svc.run(bg_db, job_id)
        except Exception as exc:
            logger.exception("Background recompute failed for job %s: %s", job_id, exc)
        finally:
            bg_db.close()

    background_tasks.add_task(_run_in_background, body.job_id)
    return RecomputeResponse(
        job_id=body.job_id,
        triggered=True,
        message="Matching pipeline queued. Poll GET /matches/{job_id} for results.",
    )
