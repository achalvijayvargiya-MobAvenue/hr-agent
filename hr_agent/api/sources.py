"""
Candidate source endpoints.

GET  /sources                          — list all registered sources with availability
POST /sources/fetch/{position_id}      — pull candidates from sources and queue extraction
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from hr_agent.api.candidates import _process_import
from hr_agent.api.deps import (
    get_current_user,
    get_db,
    get_embedding_service,
    get_extraction_service,
    get_source_registry,
)
from hr_agent.models.candidate import Candidate
from hr_agent.models.job import Job
from hr_agent.models.user import User
from hr_agent.services.candidate_service import create_import, normalize_email
from hr_agent.services.candidate_sources.registry import SourceRegistry
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionService

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

        import_row = create_import(
            db,
            raw_text=record.raw_text,
            source_name=record.source_name,
            name=record.name,
            location=record.location,
            email_hint=normalize_email(record.email),
        )
        db.flush()

        background_tasks.add_task(
            _process_import,
            import_row.id,
            extraction_svc,
            embedding_svc,
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
