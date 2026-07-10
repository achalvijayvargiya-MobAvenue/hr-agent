"""
Shared candidate ingestion logic — email-normalisation, DB writes, conflict resolution.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from hr_agent.models.candidate import Candidate
from hr_agent.models.candidate_import import CandidateImport, ImportStatus
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.services.profile_fingerprint_service import build_candidate_fingerprint
from hr_agent.services.domain_classification_service import apply_domain_to_candidate
from hr_agent.schemas.candidate import CVExtracted

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str | None) -> str | None:
    """Lowercase and strip an email address; return None if invalid."""
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized if _EMAIL_RE.match(normalized) else None


def apply_extraction_to_candidate(candidate: Candidate, extracted: CVExtracted) -> None:
    """Copy all structured fields from a CVExtracted payload onto a Candidate row."""
    candidate.name = extracted.candidate_name
    candidate.current_title = extracted.current_title
    candidate.normalized_role = extracted.normalized_role
    candidate.years_experience = extracted.years_experience
    candidate.current_company = extracted.current_company
    candidate.location = extracted.location
    candidate.skills = extracted.skills
    candidate.tools_and_technologies = extracted.tools_and_technologies
    candidate.education = [e.model_dump() for e in extracted.education]
    candidate.certifications = extracted.certifications
    candidate.employment_history = [e.model_dump() for e in extracted.employment_history]
    candidate.industries = extracted.industries
    candidate.experience_areas = extracted.experience_areas
    candidate.responsibilities = extracted.responsibilities
    candidate.seniority_level = extracted.seniority_level
    candidate.summary = extracted.summary


def create_candidate_from_extraction(
    db: Session,
    *,
    email: str,
    extracted: CVExtracted,
    raw_text: str,
    source_name: str,
) -> Candidate:
    """Insert a new Candidate keyed by email."""
    candidate = Candidate(
        email=email,
        raw_text=raw_text,
        source_name=source_name,
    )
    apply_extraction_to_candidate(candidate, extracted)
    db.add(candidate)

    log = ProcessingLog(
        entity_type="candidate",
        entity_id=email,
        status=ProcessingStatus.STRUCTURED,
    )
    db.add(log)
    return candidate


def create_candidate_from_zoho_merge(
    db: Session,
    *,
    email: str,
    merged_data,
    raw_text: str,
    zoho_submission_id: str | None = None,
    zoho_form_id: str | None = None,
) -> Candidate:
    """Insert a new Candidate keyed by email using merged data from Zoho Forms."""
    candidate = Candidate(
        email=email,
        raw_text=raw_text,
        source_name="zoho_forms",
        zoho_submission_id=zoho_submission_id,
        zoho_form_id=zoho_form_id,
        data_sources=merged_data.data_sources,
    )
    
    candidate.name = merged_data.name
    candidate.current_title = merged_data.current_title
    candidate.normalized_role = merged_data.normalized_role
    candidate.years_experience = merged_data.years_experience
    candidate.current_company = merged_data.current_company
    candidate.location = merged_data.location
    candidate.skills = merged_data.skills
    candidate.tools_and_technologies = merged_data.tools_and_technologies
    candidate.education = merged_data.education
    candidate.certifications = merged_data.certifications
    candidate.employment_history = merged_data.employment_history
    candidate.industries = merged_data.industries
    candidate.experience_areas = merged_data.experience_areas
    candidate.responsibilities = merged_data.responsibilities
    candidate.seniority_level = merged_data.seniority_level
    candidate.summary = merged_data.summary
    
    db.add(candidate)

    log = ProcessingLog(
        entity_type="candidate",
        entity_id=email,
        status=ProcessingStatus.STRUCTURED,
    )
    db.add(log)
    return candidate


def resolve_import_conflict(
    db: Session,
    import_row: CandidateImport,
    action: str,
    embedding_svc,
) -> Candidate | None:
    """
    Resolve a CONFLICT import.

    action="update" — overwrite the existing candidate with extracted data and re-embed.
    action="keep"     — discard the import; existing candidate is unchanged.

    Returns the existing Candidate on update, None on keep.
    """
    if import_row.status != ImportStatus.CONFLICT:
        raise ValueError(f"Import {import_row.id!r} is not in CONFLICT status.")

    if action == "keep":
        import_id = import_row.id
        email = import_row.proposed_email
        delete_import_row(db, import_row)
        db.commit()
        logger.info("[IMPORT] User kept existing data — import_id=%s email=%s", import_id, email)
        return None

    if action != "update":
        raise ValueError("action must be 'update' or 'keep'.")

    if not import_row.extracted_data or not import_row.proposed_email:
        raise ValueError("Import is missing extracted data.")

    extracted = CVExtracted.model_validate(import_row.extracted_data)
    candidate = db.query(Candidate).filter_by(email=import_row.proposed_email).first()
    if candidate is None:
        raise ValueError(f"Candidate {import_row.proposed_email!r} not found.")

    candidate.raw_text = import_row.raw_text
    candidate.source_name = import_row.source_name
    apply_extraction_to_candidate(candidate, extracted)

    try:
        from hr_agent.api.deps import get_domain_classification_service

        domain_svc = get_domain_classification_service()
        classification = domain_svc.classify_candidate(
            current_title=extracted.current_title,
            normalized_role=extracted.normalized_role,
            seniority_level=extracted.seniority_level,
            industries=extracted.industries,
            skills=extracted.skills,
            tools=extracted.tools_and_technologies,
            responsibilities=extracted.responsibilities,
            experience_areas=extracted.experience_areas,
            education=[e.model_dump() for e in extracted.education],
            summary=extracted.summary,
        )
        apply_domain_to_candidate(candidate, classification)
    except Exception as exc:
        logger.warning("[IMPORT] Domain classification failed on update — email=%s: %s", candidate.email, exc)

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=candidate.email, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    if log is None:
        log = ProcessingLog(entity_type="candidate", entity_id=candidate.email, status=ProcessingStatus.STRUCTURED)
        db.add(log)
    else:
        log.status = ProcessingStatus.STRUCTURED
        log.error_message = None

    db.flush()
    embedding_svc.generate_and_store(db, "candidate", candidate.email, extracted.summary)
    embedding_svc.ensure_fingerprint_embedding(
        db, "candidate", candidate.email, build_candidate_fingerprint(candidate)
    )
    if log:
        log.status = ProcessingStatus.EMBEDDED

    import_id = import_row.id
    delete_import_row(db, import_row)
    db.commit()
    logger.info("[IMPORT] User updated existing candidate — email=%s import_id=%s", candidate.email, import_id)
    return candidate


def purge_import_cv_payload(import_row: CandidateImport) -> None:
    """Remove bulky CV content from a staging row; keep only lightweight metadata."""
    import_row.raw_text = None
    import_row.extracted_data = None


def mark_import_failed(import_row: CandidateImport, error_message: str) -> None:
    """Mark an import failed and discard stored CV payload."""
    import_row.status = ImportStatus.FAILED
    import_row.error_message = error_message
    purge_import_cv_payload(import_row)


def delete_import_row(db: Session, import_row: CandidateImport) -> None:
    """Remove a staging row once it is no longer needed."""
    db.delete(import_row)


def create_import(
    db: Session,
    *,
    raw_text: str,
    source_name: str,
    name: str | None = None,
    location: str | None = None,
    email_hint: str | None = None,
) -> CandidateImport:
    """Create a pending import row for background extraction."""
    normalized_hint = normalize_email(email_hint)
    row = CandidateImport(
        id=str(uuid.uuid4()),
        raw_text=raw_text,
        source_name=source_name,
        status=ImportStatus.PROCESSING,
        name=name,
        location=location,
        proposed_email=normalized_hint,
    )
    db.add(row)
    return row
