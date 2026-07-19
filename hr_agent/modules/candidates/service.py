"""
Shared candidate ingestion logic — email-normalisation, DB writes, conflict resolution.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.candidates.import_models import CandidateImport, ImportStatus
from hr_agent.core.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.modules.matching.profile_fingerprint_service import build_candidate_fingerprint
from hr_agent.modules.taxonomy.classification_service import apply_domain_to_candidate
from hr_agent.modules.candidates.schemas import CVExtracted
from hr_agent.modules.integrations.models import JobApplication

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
    
    total_companies = len(extracted.employment_history) if extracted.employment_history else 0
    total_years = extracted.years_experience or 0.0
    if total_years > 0:
        candidate.switch_frequency = total_years / total_companies if total_companies > 0 else 0.0
    else:
        candidate.switch_frequency = None


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
        from hr_agent.core.deps import get_domain_classification_service

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
        
    save_job_application(db, candidate.email, import_row.import_metadata)

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
    import_metadata: dict | None = None,
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
        import_metadata=import_metadata,
    )
    db.add(row)
    return row


def save_job_application(db: Session, email: str, metadata: dict | None) -> None:
    if not metadata:
        return
        
    job_id = metadata.get("zoho_job_id")
    if not job_id:
        return
        
    status = metadata.get("status")
    zoho_app_id = metadata.get("zoho_application_id")
    
    app = db.query(JobApplication).filter_by(job_id=job_id, candidate_id=email).first()
    if app:
        app.status = status
        app.zoho_application_id = zoho_app_id
    else:
        app = JobApplication(
            job_id=job_id,
            candidate_id=email,
            status=status,
            zoho_application_id=zoho_app_id,
        )
        db.add(app)
    db.flush()

