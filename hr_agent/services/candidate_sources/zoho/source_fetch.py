"""
Return Zoho candidates linked to a position via job-opening mapping and applications.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.candidate import Candidate
from hr_agent.models.zoho_application import ZohoApplication
from hr_agent.models.zoho_candidate import ZohoCandidate
from hr_agent.models.zoho_job_opening import ZohoJobOpening
from hr_agent.services.candidate_sources.base import CandidateRecord
from hr_agent.services.candidate_sources.zoho.candidate_service import (
    load_demo_candidates,
    profile_to_raw_text,
    upsert_zoho_candidate,
    zoho_row_to_candidate_record,
)

logger = logging.getLogger(__name__)


def fetch_for_position(
    db: Session,
    settings: Settings,
    position_id: str,
) -> list[CandidateRecord]:
    opening = db.query(ZohoJobOpening).filter_by(mapped_job_id=position_id).first()
    if opening is None:
        if settings.zoho_demo_mode:
            return _fetch_demo_for_position(db, position_id)
        logger.info("ZohoSource: no Zoho job opening mapped to position %s.", position_id)
        return []

    applications = (
        db.query(ZohoApplication)
        .filter_by(zoho_job_opening_id=opening.zoho_id)
        .all()
    )
    if not applications:
        logger.info(
            "ZohoSource: no applications for opening %s (position %s).",
            opening.zoho_id, position_id,
        )
        return []

    records: list[CandidateRecord] = []
    for app in applications:
        row = db.query(ZohoCandidate).filter_by(zoho_id=app.zoho_candidate_id).first()
        if row is None:
            continue

        if row.local_candidate_email:
            existing = db.query(Candidate).filter_by(email=row.local_candidate_email).first()
            if existing:
                records.append(
                    CandidateRecord(
                        source_name="zoho",
                        raw_text=existing.raw_text or existing.summary or "",
                        name=existing.name,
                        location=existing.location,
                        metadata={
                            "candidate_email": existing.email,
                            "zoho_id": row.zoho_id,
                            "application_status": app.application_status,
                        },
                    )
                )
                continue

        if row.sync_status == "imported" and row.raw_profile_json:
            resume_text = row.raw_profile_json.get("_resume_text")
            if resume_text:
                records.append(
                    CandidateRecord(
                        source_name="zoho",
                        raw_text=resume_text,
                        name=row.full_name,
                        email=row.email,
                        location=(row.raw_profile_json or {}).get("City"),
                        metadata={
                            "zoho_id": row.zoho_id,
                            "position_id": position_id,
                            "application_status": app.application_status,
                        },
                    )
                )
                continue

        records.append(zoho_row_to_candidate_record(row, position_id))

    logger.info(
        "ZohoSource fetched %d record(s) for position_id=%s",
        len(records), position_id,
    )
    return records


def _fetch_demo_for_position(db: Session, position_id: str) -> list[CandidateRecord]:
    records: list[CandidateRecord] = []
    for profile in load_demo_candidates():
        row = upsert_zoho_candidate(db, profile)
        if row is None:
            continue
        db.commit()
        records.append(
            CandidateRecord(
                source_name="zoho",
                raw_text=profile_to_raw_text(profile),
                name=row.full_name,
                email=row.email,
                metadata={"zoho_id": row.zoho_id, "position_id": position_id, "demo": True},
            )
        )
    return records
