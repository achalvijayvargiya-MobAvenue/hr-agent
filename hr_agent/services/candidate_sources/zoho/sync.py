"""
Zoho Recruit sync orchestrator.

Pipeline: candidates → resumes → imports → job openings → applications.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.sync_metadata import SyncMetadata
from hr_agent.models.zoho_candidate import ZohoCandidate
from hr_agent.services.candidate_service import create_import, normalize_email
from hr_agent.services.candidate_sources.zoho.application_service import sync_applications_from_api
from hr_agent.services.candidate_sources.zoho.attachment_service import (
    apply_resume_to_row,
    download_candidate_resume_text,
)
from hr_agent.services.candidate_sources.zoho.candidate_service import sync_candidates_from_api
from hr_agent.services.candidate_sources.zoho.client import ZohoClient
from hr_agent.services.candidate_sources.zoho.job_service import sync_job_openings_from_api

logger = logging.getLogger(__name__)

ENTITY_CANDIDATES = "candidates"
ENTITY_JOB_OPENINGS = "job_openings"
ENTITY_APPLICATIONS = "applications"


def get_or_create_metadata(db: Session, entity_type: str) -> SyncMetadata:
    row = db.query(SyncMetadata).filter_by(entity_type=entity_type).first()
    if row is None:
        row = SyncMetadata(entity_type=entity_type)
        db.add(row)
        db.flush()
    return row


def get_sync_status(db: Session) -> dict:
    rows = db.query(SyncMetadata).all()
    candidate_count = db.query(ZohoCandidate).count()
    pending_count = db.query(ZohoCandidate).filter_by(sync_status="pending").count()
    imported_count = db.query(ZohoCandidate).filter_by(sync_status="imported").count()
    failed_count = db.query(ZohoCandidate).filter_by(sync_status="failed").count()

    entities = {
        row.entity_type: {
            "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "last_modified_time": row.last_modified_time,
            "status": row.status,
            "records_synced": row.records_synced,
            "error_message": row.error_message,
        }
        for row in rows
    }
    return {
        "entities": entities,
        "candidates": {
            "total": candidate_count,
            "pending": pending_count,
            "imported": imported_count,
            "failed": failed_count,
        },
    }


def _begin_entity_sync(db: Session, entity_type: str) -> SyncMetadata | None:
    meta = get_or_create_metadata(db, entity_type)
    if meta.status == "running":
        logger.warning("[ZOHO:SYNC] %s sync already running — skipping.", entity_type)
        return None
    meta.status = "running"
    meta.error_message = None
    db.flush()
    return meta


def _finish_entity_sync(
    db: Session,
    meta: SyncMetadata,
    *,
    records_synced: int,
    last_modified_time: str | None,
    error_message: str | None = None,
) -> None:
    meta.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
    meta.records_synced = records_synced
    if last_modified_time:
        meta.last_modified_time = last_modified_time
    meta.status = "failed" if error_message else "idle"
    meta.error_message = error_message


def sync_entity_records(
    db: Session,
    client: ZohoClient,
    settings: Settings,
    entity_type: str,
    sync_fn: Callable[..., tuple[int, str | None]],
) -> dict:
    meta = _begin_entity_sync(db, entity_type)
    if meta is None:
        return {"entity_type": entity_type, "skipped": True, "reason": "already running"}

    modified_since = meta.last_modified_time
    try:
        count, latest = sync_fn(
            db, client, settings, modified_since=modified_since,
        )
        _finish_entity_sync(db, meta, records_synced=count, last_modified_time=latest)
        db.commit()
        logger.info("[ZOHO:SYNC] %s synced %d record(s).", entity_type, count)
        return {"entity_type": entity_type, "records_synced": count, "skipped": False}
    except Exception as exc:
        db.rollback()
        meta = get_or_create_metadata(db, entity_type)
        _finish_entity_sync(db, meta, records_synced=0, last_modified_time=modified_since, error_message=str(exc))
        db.commit()
        logger.exception("[ZOHO:SYNC] %s sync failed: %s", entity_type, exc)
        return {"entity_type": entity_type, "skipped": False, "error": str(exc)}


def process_pending_candidate_imports(
    db: Session,
    client: ZohoClient,
    settings: Settings,
    *,
    import_processor: Callable[[str], None] | None = None,
    limit: int = 50,
) -> dict:
    """
    Download resumes for pending Zoho candidates and queue them through the import pipeline.

    import_processor: callable(import_id) — typically _process_import for background embedding.
    """
    pending_rows = (
        db.query(ZohoCandidate)
        .filter(ZohoCandidate.sync_status.in_(["pending", "failed"]))
        .limit(limit)
        .all()
    )

    queued = 0
    failed = 0

    for row in pending_rows:
        profile = row.raw_profile_json or {}
        raw_text, attachment_id = download_candidate_resume_text(
            client, row.zoho_id, profile, demo_mode=settings.zoho_demo_mode,
        )
        if not raw_text:
            row.sync_status = "failed"
            row.sync_error = "No resume text or profile content available."
            failed += 1
            continue

        apply_resume_to_row(row, raw_text, attachment_id)

        import_row = create_import(
            db,
            raw_text=raw_text,
            source_name="zoho",
            name=row.full_name,
            location=profile.get("City"),
            email_hint=normalize_email(row.email),
        )
        db.flush()

        if import_processor:
            try:
                import_processor(import_row.id)
            except Exception as exc:
                row.sync_status = "failed"
                row.sync_error = str(exc)
                failed += 1
                logger.error("[ZOHO:SYNC] Import processing failed for %s: %s", row.zoho_id, exc)
                continue

            db.refresh(import_row)
            from hr_agent.models.candidate_import import ImportStatus

            if import_row.status == ImportStatus.CONFLICT:
                row.sync_status = "conflict"
                if import_row.proposed_email:
                    row.local_candidate_email = import_row.proposed_email
                row.sync_error = "Duplicate email — awaiting user resolution."
                queued += 1
                continue
            if import_row.status == ImportStatus.FAILED:
                row.sync_status = "failed"
                row.sync_error = import_row.error_message or "Import failed."
                failed += 1
                continue

        row.sync_status = "imported"
        if import_row.proposed_email:
            row.local_candidate_email = import_row.proposed_email
        row.sync_error = None
        queued += 1

    db.commit()
    return {"processed": queued, "failed": failed}


def run_full_sync(
    db: Session,
    client: ZohoClient,
    settings: Settings,
    *,
    import_processor: Callable[[str], None] | None = None,
) -> dict:
    """Run the full Zoho sync pipeline."""
    if not settings.zoho_demo_mode and not client.auth.is_configured():
        return {"ok": False, "error": "Zoho OAuth is not configured."}

    results: dict = {"ok": True, "steps": []}

    for entity_type, sync_fn in (
        (ENTITY_CANDIDATES, sync_candidates_from_api),
        (ENTITY_JOB_OPENINGS, sync_job_openings_from_api),
        (ENTITY_APPLICATIONS, sync_applications_from_api),
    ):
        if settings.zoho_demo_mode and entity_type != ENTITY_CANDIDATES:
            results["steps"].append({
                "entity_type": entity_type,
                "skipped": True,
                "reason": "demo mode — candidates only",
            })
            continue
        step = sync_entity_records(db, client, settings, entity_type, sync_fn)
        results["steps"].append(step)
        if step.get("error"):
            results["ok"] = False

    resume_step = process_pending_candidate_imports(
        db, client, settings, import_processor=import_processor,
    )
    results["steps"].append({"entity_type": "resume_imports", **resume_step})

    logger.info("[ZOHO:SYNC] Full sync complete — %s", results)
    return results
