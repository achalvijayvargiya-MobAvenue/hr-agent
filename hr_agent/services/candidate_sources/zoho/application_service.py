"""Sync Zoho Applications into local mirror."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.zoho_application import ZohoApplication
from hr_agent.services.candidate_sources.zoho.client import ZohoClient

logger = logging.getLogger(__name__)


def _lookup_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        inner = value.get("id") or value.get("name")
        return str(inner) if inner else None
    return str(value)


def upsert_application(db: Session, record: dict[str, Any]) -> ZohoApplication | None:
    zoho_id = record.get("id")
    if not zoho_id:
        return None

    candidate_id = _lookup_id(record.get("Candidate_Name") or record.get("$Candidate_Name"))
    job_id = _lookup_id(record.get("Job_Opening_Name") or record.get("$Job_Opening_Name"))
    if not candidate_id or not job_id:
        logger.debug("[ZOHO:APP] Skipping application %s — missing candidate/job refs.", zoho_id)
        return None

    row = db.query(ZohoApplication).filter_by(zoho_id=str(zoho_id)).first()
    if row is None:
        row = ZohoApplication(zoho_id=str(zoho_id))
        db.add(row)

    row.zoho_candidate_id = candidate_id
    row.zoho_job_opening_id = job_id
    row.application_status = record.get("Application_Status") or record.get("Status")
    modified = record.get("Modified_Time")
    row.modified_time = str(modified) if modified else row.modified_time
    return row


def sync_applications_from_api(
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
        payload = client.list_applications(
            page=page,
            per_page=settings.zoho_sync_page_size,
            modified_since=modified_since,
        )
        records = payload.get("data") or []
        if not records:
            break

        for record in records:
            row = upsert_application(db, record)
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
