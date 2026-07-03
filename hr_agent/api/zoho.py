"""
Zoho Recruit integration endpoints.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from hr_agent.api.candidates import _process_import
from hr_agent.api.deps import (
    get_current_user,
    get_db,
    get_embedding_service,
    get_extraction_service,
    get_settings,
    get_source_registry,
    require_role,
)
from hr_agent.config import Settings
from hr_agent.models.job import Job
from hr_agent.models.user import User
from hr_agent.models.zoho_job_opening import ZohoJobOpening
from hr_agent.services.candidate_sources.registry import SourceRegistry
from hr_agent.services.candidate_sources.zoho.client import ZohoClient
from hr_agent.services.candidate_sources.zoho.source import ZohoSource
from hr_agent.services.candidate_sources.zoho.sync import get_sync_status, run_full_sync
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sources/zoho", tags=["zoho"])


class JobMappingRequest(BaseModel):
    zoho_job_opening_id: str
    job_id: str


def _get_zoho_source(registry: SourceRegistry) -> ZohoSource:
    source = registry.get("zoho")
    if source is None or not isinstance(source, ZohoSource):
        raise HTTPException(status_code=503, detail="Zoho source is not registered.")
    return source


@router.get("/health", dependencies=[Depends(get_current_user)])
def zoho_health(
    registry: SourceRegistry = Depends(get_source_registry),
) -> dict:
    source = _get_zoho_source(registry)
    return source.client.health_check()


@router.get("/status", dependencies=[Depends(get_current_user)])
def zoho_status(db: Session = Depends(get_db)) -> dict:
    return get_sync_status(db)


@router.post("/sync", dependencies=[Depends(require_role("admin"))])
def trigger_zoho_sync(
    background_tasks: BackgroundTasks,
    registry: SourceRegistry = Depends(get_source_registry),
    settings: Settings = Depends(get_settings),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
) -> dict:
    """Trigger a manual Zoho sync (admin only). Runs in the background."""
    source = _get_zoho_source(registry)
    if not source.is_available():
        raise HTTPException(status_code=503, detail="Zoho source is not configured.")

    def _run_sync() -> None:
        from hr_agent.database import SessionLocal

        def import_processor(import_id: str) -> None:
            _process_import(import_id, extraction_svc, embedding_svc)

        sync_db = SessionLocal()
        try:
            run_full_sync(sync_db, source.client, settings, import_processor=import_processor)
        finally:
            sync_db.close()

    background_tasks.add_task(_run_sync)
    logger.info("[API:ZOHO] Manual sync queued.")
    return {"status": "queued", "message": "Zoho sync started in the background."}


@router.get("/job-openings", dependencies=[Depends(get_current_user)])
def list_zoho_job_openings(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(ZohoJobOpening).order_by(ZohoJobOpening.posting_title).all()
    return [
        {
            "zoho_id": row.zoho_id,
            "posting_title": row.posting_title,
            "mapped_job_id": row.mapped_job_id,
            "modified_time": row.modified_time,
        }
        for row in rows
    ]


@router.post("/job-mappings", dependencies=[Depends(require_role("admin"))])
def create_job_mapping(
    body: JobMappingRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    opening = db.query(ZohoJobOpening).filter_by(zoho_id=body.zoho_job_opening_id).first()
    if opening is None:
        raise HTTPException(status_code=404, detail=f"Zoho job opening {body.zoho_job_opening_id!r} not found.")

    job = db.query(Job).filter_by(id=body.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Position {body.job_id!r} not found.")

    db.query(ZohoJobOpening).filter(
        ZohoJobOpening.mapped_job_id == body.job_id,
        ZohoJobOpening.zoho_id != body.zoho_job_opening_id,
    ).update({"mapped_job_id": None})

    opening.mapped_job_id = body.job_id
    db.commit()

    return {
        "zoho_id": opening.zoho_id,
        "posting_title": opening.posting_title,
        "mapped_job_id": opening.mapped_job_id,
    }
