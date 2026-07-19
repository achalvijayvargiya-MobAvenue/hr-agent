"""
Candidate source endpoints.

GET  /sources                          — list all registered sources with availability
POST /sources/fetch/{position_id}      — pull candidates from sources and queue extraction
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from hr_agent.modules.candidates.api import _process_import
from hr_agent.core.deps import (
    get_current_user,
    get_db,
    get_embedding_service,
    get_extraction_service,
    get_source_registry,
)
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.users.models import User
from hr_agent.modules.candidates.service import create_import, normalize_email
from hr_agent.modules.integrations.candidate_sources.registry import SourceRegistry
from hr_agent.modules.integrations.models import JobApplication
from hr_agent.core.services.embedding_service import EmbeddingService
from hr_agent.core.services.extraction_service import ExtractionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", dependencies=[Depends(get_current_user)])
def list_sources(
    registry: SourceRegistry = Depends(get_source_registry),
) -> list[dict]:
    """Return all registered candidate sources with name, display_name, and availability."""
    all_sources = list(registry._sources.values())
    return [
        {
            "name": s.name,
            "display_name": s.display_name,
            "is_available": s.is_available(),
        }
        for s in all_sources
    ]


@router.post("/fetch/{position_id}")
def fetch_candidates_for_position(
    position_id: str,
    background_tasks: BackgroundTasks,
    source_names: list[str] | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: SourceRegistry = Depends(get_source_registry),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
) -> dict:
    """
    Fetch candidates for a position from all available sources (or a named subset).
    New candidates are queued for LLM extraction. Duplicate emails surface as conflicts
    for the user to resolve (update existing or keep old data).
    """
    job = db.query(Job).filter_by(id=position_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id!r} not found.")

    records = registry.fetch_all(position_id, source_names=source_names)

    sources_queried = (
        source_names
        if source_names
        else [s.name for s in registry.list_available()]
    )

    new_count = 0
    for record in records:
        if record.metadata.get("candidate_email") is not None:
            continue

        email_hint = normalize_email(record.email)
        if email_hint:
            existing = db.query(Candidate).filter_by(email=email_hint).first()
            if existing:
                logger.info(
                    "[API:SOURCES] Candidate %s already exists. Skipping LLM extraction to save cost.", 
                    email_hint
                )
                try:
                    from hr_agent.core.events import bus
                    payload = {
                        "position_id": position_id,
                        "candidate_email": email_hint
                    }
                    bus.emit("CandidateImported", payload)
                except Exception as e:
                    logger.error("[API:SOURCES] Failed to emit CandidateImported event for %s: %s", email_hint, e)
                continue

        import_row = create_import(
            db,
            raw_text=record.raw_text,
            source_name=record.source_name,
            name=record.name,
            location=record.location,
            email_hint=email_hint,
            import_metadata=record.metadata,
        )
        db.flush()

        background_tasks.add_task(
            _process_import,
            import_row.id,
            extraction_svc,
            embedding_svc,
            position_id=position_id,
        )
        new_count += 1

    db.commit()

    logger.info(
        "[API:SOURCES] fetch position_id=%s  sources=%s  records=%d  new_imports=%d",
        position_id, sources_queried, len(records), new_count,
    )

    return {
        "position_id": position_id,
        "sources_queried": sources_queried,
        "total_records": len(records),
        "new_candidates": new_count,
    }


@router.post("/zoho/webhook")
async def zoho_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive live status updates from Zoho Recruit Webhooks.
    Zoho webhooks must be configured to send a POST request with the following JSON/Form fields:
    - candidate_id (or Candidate_Id)
    - job_id (or Job_Id)
    - status (or Application_Status)
    """
    try:
        if request.headers.get("content-type") == "application/json":
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)
            
        logger.info(f"[ZOHO WEBHOOK] Received payload: {payload}")
        
        # Zoho might send varying field names based on webhook config
        zoho_candidate_id = payload.get("candidate_id") or payload.get("Candidate_Id")
        status = payload.get("status") or payload.get("Application_Status")
        
        # We might receive our internal candidate email or job id if we passed it along, 
        # but usually we only have zoho application id or zoho candidate id + zoho job id.
        # If Zoho sends zoho_application_id
        app_id = payload.get("zoho_application_id") or payload.get("id") or payload.get("Application_Id")
        
        # We need to find the JobApplication by zoho_application_id if we have it
        app = None
        if app_id:
            app = db.query(JobApplication).filter_by(zoho_application_id=app_id).first()
            
        if not app and zoho_candidate_id:
             # Find by zoho_candidate_id and zoho_job_id (this requires joining candidates if we stored zoho_candidate_id, 
             # but we didn't store it on candidate. We stored it in import_metadata, which is gone. 
             # Wait, JobApplication only has candidate_email, job_id, zoho_application_id, status.
             # So we MUST rely on zoho_application_id or pass internal ids.
             pass
             
        if not app and payload.get("internal_candidate_email") and payload.get("internal_job_id"):
            app = db.query(JobApplication).filter_by(
                candidate_id=payload.get("internal_candidate_email"),
                job_id=payload.get("internal_job_id")
            ).first()

        if app:
            app.status = status
            db.commit()
            
            # Emit event to EventBus for SSE clients
            try:
                from hr_agent.core.events import bus
                bus.emit("ApplicationStatusChanged", {
                    "job_id": app.job_id,
                    "candidate_email": app.candidate_id,
                    "status": app.status
                })
            except Exception as e:
                logger.error(f"[ZOHO WEBHOOK] Failed to emit event: {e}")
                
            return {"status": "ok", "message": "Updated application status"}
        else:
            logger.warning(f"[ZOHO WEBHOOK] Could not find JobApplication for payload: {payload}")
            return {"status": "ok", "message": "JobApplication not found, ignored"}
            
    except Exception as e:
        logger.error(f"[ZOHO WEBHOOK] Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

