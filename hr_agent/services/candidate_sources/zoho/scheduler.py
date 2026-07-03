"""
Background scheduler for periodic Zoho incremental sync.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from hr_agent.config import Settings, get_settings
from hr_agent.database import SessionLocal
from hr_agent.services.candidate_sources.zoho.auth import ZohoAuthManager
from hr_agent.services.candidate_sources.zoho.client import ZohoClient
from hr_agent.services.candidate_sources.zoho.sync import run_full_sync

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_scheduled_sync() -> None:
    settings = get_settings()
    if not settings.zoho_sync_enabled:
        return
    if not settings.zoho_demo_mode and not (
        settings.zoho_client_id and settings.zoho_client_secret and settings.zoho_refresh_token
    ):
        logger.warning("[ZOHO:SCHEDULER] Sync skipped — OAuth not configured.")
        return

    from hr_agent.api.candidates import _process_import
    from hr_agent.api.deps import get_embedding_service, get_extraction_service

    extraction_svc = get_extraction_service()
    embedding_svc = get_embedding_service()
    auth = ZohoAuthManager(settings)
    client = ZohoClient(settings, auth)

    def import_processor(import_id: str) -> None:
        _process_import(import_id, extraction_svc, embedding_svc)

    db = SessionLocal()
    try:
        logger.info("[ZOHO:SCHEDULER] Starting scheduled sync.")
        run_full_sync(db, client, settings, import_processor=import_processor)
    except Exception as exc:
        logger.exception("[ZOHO:SCHEDULER] Scheduled sync failed: %s", exc)
    finally:
        db.close()


def start_zoho_scheduler(settings: Settings) -> BackgroundScheduler | None:
    global _scheduler
    if not settings.zoho_sync_enabled:
        logger.info("[ZOHO:SCHEDULER] Disabled — set ZOHO_SYNC_ENABLED=true to enable.")
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_scheduled_sync,
        trigger="interval",
        minutes=settings.zoho_sync_interval_minutes,
        id="zoho_incremental_sync",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "[ZOHO:SCHEDULER] Started — interval=%d min",
        settings.zoho_sync_interval_minutes,
    )
    return _scheduler


def stop_zoho_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[ZOHO:SCHEDULER] Stopped.")
