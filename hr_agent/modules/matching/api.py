"""
Matching routes.

GET  /matches/{job_id}  — return ranked candidates for a job (runs pipeline if no results exist)
POST /recompute-match   — force a fresh pipeline run for a job
"""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json

from hr_agent.core.deps import get_current_user, get_db, get_matching_service
from hr_agent.core.config import get_settings
from hr_agent.core.errors import NotFoundError
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.matching.models import MatchResult
from hr_agent.modules.matching.schemas import MatchEntry, MatchResponse, RecomputeRequest, RecomputeResponse, ScoreBreakdown
from hr_agent.modules.matching.service import MatchingService
from hr_agent.modules.integrations.models import JobApplication

logger = logging.getLogger(__name__)
router = APIRouter(tags=["matches"], dependencies=[Depends(get_current_user)])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _build_match_response(job_id: str, results: list[MatchResult], db: Session) -> MatchResponse:
    cand_ids = [r.candidate_id for r in results]
    candidates = db.query(Candidate).filter(Candidate.email.in_(cand_ids)).all()
    name_map: dict[str, str | None] = {c.email: c.name for c in candidates}
    source_map: dict[str, str | None] = {c.email: c.source_name for c in candidates}
    switch_map: dict[str, float | None] = {c.email: getattr(c, "switch_frequency", None) for c in candidates}
    exp_map: dict[str, float | None] = {c.email: getattr(c, "years_experience", None) for c in candidates}
    
    apps = db.query(JobApplication).filter(JobApplication.job_id == job_id, JobApplication.candidate_id.in_(cand_ids)).all()
    app_status_map: dict[str, str | None] = {app.candidate_id: app.status for app in apps}

    from hr_agent.modules.jobs.models import Job
    job = db.query(Job).filter(Job.id == job_id).first()
    job_pref = [p.lower() for p in (job.preferred_companies or []) if p] if job else []
    
    matched_pref_map: dict[str, list[str]] = {}
    for c in candidates:
        matched = []
        if job_pref and c.employment_history:
            for exp in c.employment_history:
                comp = (exp.get("company") or "").strip()
                if comp and any(p in comp.lower() for p in job_pref):
                    matched.append(comp)
        matched_pref_map[c.email] = list(set(matched))

    settings = get_settings()
    sw = settings.score_weights
    fsw = settings.final_score_weights
    phase4 = settings.llm_explanation_only

    ranked = sorted(
        [r for r in results if not r.is_filtered and r.final_score is not None],
        key=lambda r: r.final_score,
        reverse=True,
    )

    entries: list[MatchEntry] = []
    rank = 1
    for result in ranked:
        if phase4:
            summary = (
                f"{int(fsw.requirement_fit * 100)}% fit + "
                f"{int(fsw.retrieval * 100)}% retrieval + "
                f"{int(fsw.rerank * 100)}% rerank = {result.final_score:.2f}"
                if result.final_score is not None
                else "N/A"
            )
            breakdown = ScoreBreakdown(
                rule_score=result.rule_score,
                vector_score=result.vector_score,
                rerank_score=result.rerank_score,
                llm_score=None,
                final_score=result.final_score,
                requirement_fit_score=result.requirement_fit_score,
                rule_weight=0.0,
                vector_weight=fsw.retrieval,
                rerank_weight=fsw.rerank,
                requirement_fit_weight=fsw.requirement_fit,
                llm_weight=0.0,
                summary=summary,
            )
        else:
            breakdown = ScoreBreakdown(
                rule_score=result.rule_score,
                vector_score=result.vector_score,
                rerank_score=result.rerank_score,
                llm_score=result.llm_score,
                final_score=result.final_score,
                requirement_fit_score=result.requirement_fit_score,
                rule_weight=sw.rule,
                vector_weight=sw.vector,
                rerank_weight=None,
                requirement_fit_weight=None,
                llm_weight=sw.llm,
                summary=(
                    f"{int(sw.rule * 100)}% rule + {int(sw.vector * 100)}% vector + "
                    f"{int(sw.llm * 100)}% LLM = {result.final_score:.2f}"
                    if result.final_score is not None
                    else "N/A"
                ),
            )
        entries.append(
            MatchEntry(
                rank=rank,
                candidate_id=result.candidate_id,
                candidate_name=name_map.get(result.candidate_id),
                is_filtered=False,
                filter_reason=None,
                requirement_fit_score=result.requirement_fit_score,
                requirement_gaps=None,
                rule_score=result.rule_score,
                vector_score=result.vector_score,
                rerank_score=result.rerank_score,
                llm_score=result.llm_score,
                final_score=result.final_score,
                explanation=result.explanation,
                source_name=source_map.get(result.candidate_id),
                application_status=app_status_map.get(result.candidate_id),
                switch_frequency=switch_map.get(result.candidate_id),
                years_experience=exp_map.get(result.candidate_id),
                matched_preferred_companies=matched_pref_map.get(result.candidate_id, []),
                score_breakdown=breakdown,
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
                    requirement_fit_score=result.requirement_fit_score,
                    requirement_gaps=result.requirement_gaps,
                    rule_score=None,
                    vector_score=None,
                    rerank_score=None,
                    llm_score=None,
                    final_score=None,
                    explanation=None,
                    source_name=source_map.get(result.candidate_id),
                    application_status=app_status_map.get(result.candidate_id),
                    switch_frequency=switch_map.get(result.candidate_id),
                    years_experience=exp_map.get(result.candidate_id),
                    matched_preferred_companies=matched_pref_map.get(result.candidate_id, []),
                )
            )
    valid_dates = [r.computed_at for r in results if r.computed_at is not None]
    latest_at = max(valid_dates) if valid_dates else None

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
    top_k: int | None = Query(default=None, description="Return at most this many ranked results"),
    source_filter: str | None = Query(default=None, description="Comma-separated source names to include, e.g. local_kb,github"),
    db: Session = Depends(get_db),
    matching_svc: MatchingService = Depends(get_matching_service),
):
    """
    Return ranked candidates for the given job.
    If no match results exist yet, runs the full pipeline synchronously first.
    Use top_k to cap the result count and source_filter to restrict by source.
    """
    source_list = [s.strip() for s in source_filter.split(",")] if source_filter else None

    existing = db.query(MatchResult).filter_by(job_id=job_id).all()
    if existing:
        return _build_match_response(job_id, existing, db)

    # No cached results — run now
    try:
        results = matching_svc.run(db, job_id, source_filter=source_list, top_k=top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Matching pipeline failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Matching pipeline error: {exc}") from exc

    return _build_match_response(job_id, results, db)


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
    Optionally pass source_filter (list of source names) and top_k.
    """
    from hr_agent.modules.jobs.models import Job  # avoid circular at module level

    job = db.query(Job).filter_by(id=body.job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {body.job_id!r} not found.")

    def _run_in_background(job_id: str, source_filter: list[str] | None, top_k: int | None) -> None:
        from hr_agent.core.database import SessionLocal

        bg_db = SessionLocal()
        try:
            matching_svc.run(bg_db, job_id, source_filter=source_filter, top_k=top_k, refresh=True)
        except Exception as exc:
            logger.exception("Background recompute failed for job %s: %s", job_id, exc)
        finally:
            bg_db.close()

    background_tasks.add_task(_run_in_background, body.job_id, body.source_filter, body.top_k)
    return RecomputeResponse(
        job_id=body.job_id,
        triggered=True,
        message="Matching pipeline queued. Poll GET /matches/{job_id} for results.",
    )


@router.post("/matches/{job_id}/sync-status")
def sync_zoho_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    On-demand sync of candidate application statuses from Zoho for this job.
    Updates the local JobApplication table and returns the count of updated statuses.
    """
    from hr_agent.modules.jobs.models import Job
    from hr_agent.modules.integrations.zoho.client import ZohoRecruitClient
    from hr_agent.modules.integrations.models import JobApplication
    from hr_agent.core.events import bus

    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise NotFoundError(message=f"Job {job_id!r} not found.")
        
    zoho_id = job.zoho_id
    if not zoho_id:
        return {"status": "skipped", "message": "Job is not linked to Zoho Recruit."}

    client = ZohoRecruitClient()
    logger.info(f"Syncing statuses for job {job_id} (Zoho ID: {zoho_id})")
    applications = client.get_applications_for_job(zoho_id)
    
    if not applications:
        return {"status": "ok", "updated": 0, "message": "No applications found in Zoho."}
        
    updated_count = 0
    for app_data in applications:
        z_app_id = app_data.get("id")
        status = app_data.get("Application_Status")
        z_cand_id = app_data.get("$Candidate_Id")
        
        if not z_app_id or not status:
            continue
            
        app = db.query(JobApplication).filter_by(zoho_application_id=z_app_id).first()
        
        if not app and z_cand_id:
            details = client.get_candidate_details(z_cand_id)
            if details and details.get("Email"):
                from hr_agent.modules.candidates.service import normalize_email
                from hr_agent.modules.candidates.models import Candidate
                email_hint = normalize_email(details.get("Email"))
                if email_hint and db.query(Candidate).filter_by(email=email_hint).first():
                    app = db.query(JobApplication).filter_by(job_id=job_id, candidate_id=email_hint).first()
                    if app:
                        app.zoho_application_id = z_app_id
                    else:
                        app = JobApplication(
                            job_id=job_id,
                            candidate_id=email_hint,
                            status=status,
                            zoho_application_id=z_app_id
                        )
                        db.add(app)
                        # We just created it, so count it as updated
                        updated_count += 1
                        
        if app:
            if app.status != status or app in db.new:
                app.status = status
                updated_count += 1
                try:
                    bus.emit("ApplicationStatusChanged", {
                        "job_id": app.job_id,
                        "candidate_email": app.candidate_id,
                        "status": app.status
                    })
                except Exception as e:
                    logger.error(f"Failed to emit status event during sync: {e}")

    db.commit()
    return {"status": "ok", "updated": updated_count, "message": f"Successfully synced {updated_count} statuses."}


@router.get("/matches/{job_id}/live")
async def live_matches(job_id: str, request: Request):
    """
    Server-Sent Events endpoint to stream real-time candidate application status updates
    for a specific job from Zoho webhook to the frontend.
    """
    from hr_agent.core.events import bus

    async def event_generator():
        # Create an async queue for this client
        queue = asyncio.Queue()
        
        # Define a callback that puts events into the queue
        def on_status_change(payload):
            if payload.get("job_id") == job_id:
                # We need to run it thread-safe since bus.emit might be from a sync context
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(queue.put_nowait, payload)

        # Subscribe to the event
        bus.on("ApplicationStatusChanged", on_status_change)
        
        try:
            while True:
                # Wait for a connection drop or a new event
                if await request.is_disconnected():
                    break
                    
                try:
                    # Wait for an event with a timeout so we can check disconnects
                    payload = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    continue
        finally:
            bus.off("ApplicationStatusChanged", on_status_change)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

