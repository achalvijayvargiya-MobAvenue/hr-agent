"""
Map Zoho candidate API records to local DB rows and CandidateRecord payloads.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.zoho_candidate import ZohoCandidate
from hr_agent.services.candidate_service import normalize_email
from hr_agent.services.candidate_sources.base import CandidateRecord
from hr_agent.services.candidate_sources.zoho.client import ZohoClient

logger = logging.getLogger(__name__)

_DEMO_DATA_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "zoho_demo_candidates.json")
)


def extract_zoho_id(record: dict[str, Any]) -> str | None:
    zoho_id = record.get("id")
    if zoho_id:
        return str(zoho_id)
    return None


def extract_email(record: dict[str, Any]) -> str | None:
    for key in ("Email", "Secondary_Email"):
        value = record.get(key)
        normalized = normalize_email(value if isinstance(value, str) else None)
        if normalized:
            return normalized
    return None


def extract_full_name(record: dict[str, Any]) -> str | None:
    for key in ("Full_Name", "Candidate_Name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    first = (record.get("First_Name") or "").strip()
    last = (record.get("Last_Name") or "").strip()
    combined = f"{first} {last}".strip()
    return combined or None


def extract_modified_time(record: dict[str, Any]) -> str | None:
    value = record.get("Modified_Time")
    return str(value) if value else None


def profile_to_raw_text(record: dict[str, Any]) -> str:
    """Build CV-like text from Zoho structured fields when no resume is available."""
    lines = [
        f"Name: {extract_full_name(record) or 'Unknown'}",
    ]
    email = extract_email(record)
    if email:
        lines.append(f"Email: {email}")
    for label, key in (
        ("Current Title", "Current_Job_Title"),
        ("Current Employer", "Current_Employer"),
        ("Experience", "Experience_in_Years"),
        ("Location", "City"),
        ("Skills", "Skill_Set"),
        ("Highest Qualification", "Highest_Qualification_Held"),
    ):
        value = record.get(key)
        if value:
            lines.append(f"{label}: {value}")
    summary = record.get("Additional_Info") or record.get("Summary")
    if summary:
        lines.append(f"\nSummary:\n{summary}")
    return "\n".join(lines)


def upsert_zoho_candidate(db: Session, record: dict[str, Any]) -> ZohoCandidate | None:
    zoho_id = extract_zoho_id(record)
    if not zoho_id:
        return None

    row = db.query(ZohoCandidate).filter_by(zoho_id=zoho_id).first()
    modified_time = extract_modified_time(record)
    email = extract_email(record)
    full_name = extract_full_name(record)

    if row and row.modified_time == modified_time and row.sync_status == "imported":
        return row

    if row is None:
        row = ZohoCandidate(zoho_id=zoho_id)
        db.add(row)

    row.email = email
    row.full_name = full_name
    row.modified_time = modified_time
    row.raw_profile_json = record
    if row.sync_status in ("imported", "conflict"):
        row.sync_status = "pending"
    elif row.sync_status == "failed":
        row.sync_status = "pending"
        row.sync_error = None
    return row


def load_demo_candidates() -> list[dict[str, Any]]:
    if not os.path.isfile(_DEMO_DATA_FILE):
        logger.warning("Zoho demo data file not found at %r", _DEMO_DATA_FILE)
        return []
    with open(_DEMO_DATA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def sync_candidates_from_api(
    db: Session,
    client: ZohoClient,
    settings: Settings,
    *,
    modified_since: str | None = None,
) -> tuple[int, str | None]:
    """Paginate Zoho /Candidates and upsert local mirror rows."""
    if settings.zoho_demo_mode:
        records = load_demo_candidates()
        count = 0
        latest_modified: str | None = modified_since
        for record in records:
            row = upsert_zoho_candidate(db, record)
            if row:
                count += 1
                mt = extract_modified_time(record)
                if mt and (latest_modified is None or mt > latest_modified):
                    latest_modified = mt
        return count, latest_modified

    page = 1
    total = 0
    latest_modified = modified_since

    while True:
        payload = client.list_candidates(
            page=page,
            per_page=settings.zoho_sync_page_size,
            modified_since=modified_since,
        )
        records = payload.get("data") or []
        if not records:
            break

        for record in records:
            row = upsert_zoho_candidate(db, record)
            if row:
                total += 1
                mt = extract_modified_time(record)
                if mt and (latest_modified is None or mt > latest_modified):
                    latest_modified = mt

        info = payload.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1

    return total, latest_modified


def zoho_row_to_candidate_record(row: ZohoCandidate, position_id: str) -> CandidateRecord:
    profile = row.raw_profile_json or {}
    raw_text = profile_to_raw_text(profile)
    return CandidateRecord(
        source_name="zoho",
        raw_text=raw_text,
        source_url=None,
        name=row.full_name,
        email=row.email,
        location=profile.get("City"),
        metadata={
            "zoho_id": row.zoho_id,
            "position_id": position_id,
            "application_status": profile.get("Application_Status"),
        },
    )
