"""Sync Zoho Job Openings into local mirror."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.zoho_job_opening import ZohoJobOpening
from hr_agent.services.candidate_sources.zoho.client import ZohoClient

logger = logging.getLogger(__name__)


def _extract_id(record: dict[str, Any]) -> str | None:
    value = record.get("id")
    return str(value) if value else None


def upsert_job_opening(db: Session, record: dict[str, Any]) -> ZohoJobOpening | None:
    zoho_id = _extract_id(record)
    if not zoho_id:
        return None

    row = db.query(ZohoJobOpening).filter_by(zoho_id=zoho_id).first()
    if row is None:
        row = ZohoJobOpening(zoho_id=zoho_id)
        db.add(row)

    row.posting_title = record.get("Posting_Title") or record.get("Job_Opening_Name")
    modified = record.get("Modified_Time")
    row.modified_time = str(modified) if modified else row.modified_time
    row.raw_json = record
    return row


def sync_job_openings_from_api(
    db: Session,
    client: ZohoClient,
    settings: Settings,
    *,
    modified_since: str | None = None,
) -> tuple[int, str | None]:
    page = 1
    total = 0
    latest_modified = modified_since

    while True:
        payload = client.list_job_openings(
            page=page,
            per_page=settings.zoho_sync_page_size,
            modified_since=modified_since,
        )
        records = payload.get("data") or []
        if not records:
            break

        for record in records:
            row = upsert_job_opening(db, record)
            if row:
                total += 1
                mt = record.get("Modified_Time")
                if mt:
                    mt_str = str(mt)
                    if latest_modified is None or mt_str > latest_modified:
                        latest_modified = mt_str

        info = payload.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1

    return total, latest_modified
