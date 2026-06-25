"""
Candidate routes.

POST /candidates/upload              — accept a CV PDF, queue background processing
GET  /candidates/imports             — list in-flight imports and email conflicts
GET  /candidates/imports/conflicts   — list pending duplicate-email conflicts
POST /candidates/imports/{id}/resolve — update existing or keep old data
GET  /candidates/{email}             — return the structured candidate record
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from hr_agent.api.deps import (
    extract_pdf_text,
    get_current_user,
    get_db,
    get_embedding_service,
    get_extraction_service,
)
from hr_agent.core.errors import NotFoundError
from hr_agent.models.candidate import Candidate
from hr_agent.models.candidate_import import CandidateImport, ImportStatus
from hr_agent.models.embedding import Embedding
from hr_agent.models.match_result import MatchResult
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.schemas.candidate import (
    CandidateConflictResponse,
    CandidateImportResponse,
    CandidateResponse,
    CandidateUploadResponse,
    ResolveImportRequest,
)
from hr_agent.services.candidate_service import (
    create_candidate_from_extraction,
    create_import,
    delete_import_row,
    mark_import_failed,
    normalize_email,
    resolve_import_conflict,
)
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.services.pdf_service import PDFExtractionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"], dependencies=[Depends(get_current_user)])


def _candidate_response(candidate: Candidate, status: str) -> CandidateResponse:
    return CandidateResponse(
        email=candidate.email,
        name=candidate.name,
        current_title=candidate.current_title,
        normalized_role=candidate.normalized_role,
        years_experience=candidate.years_experience,
        current_company=candidate.current_company,
        location=candidate.location,
        skills=candidate.skills or [],
        tools_and_technologies=candidate.tools_and_technologies or [],
        education=candidate.education or [],
        certifications=candidate.certifications or [],
        employment_history=candidate.employment_history or [],
        industries=candidate.industries or [],
        experience_areas=candidate.experience_areas or [],
        responsibilities=candidate.responsibilities or [],
        seniority_level=candidate.seniority_level,
        summary=candidate.summary,
        source_name=candidate.source_name or "local_kb",
        status=status,
        created_at=candidate.created_at,
    )


def _import_response(row: CandidateImport) -> CandidateImportResponse:
    return CandidateImportResponse(
        import_id=row.id,
        status=row.status,
        source_name=row.source_name,
        proposed_email=row.proposed_email,
        existing_email=row.existing_email,
        name=row.name,
        location=row.location,
        extracted_data=row.extracted_data,
        error_message=row.error_message,
        created_at=row.created_at,
    )


# ── Background task ────────────────────────────────────────────────────────────

def _process_import(
    import_id: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """Background task: LLM extraction → duplicate check → create or flag conflict."""
    from hr_agent.database import SessionLocal

    logger.info("[BG:CV] Background processing started — import_id: %s", import_id)
    db = SessionLocal()
    try:
        import_row = db.query(CandidateImport).filter_by(id=import_id).first()
        if import_row is None:
            logger.error("[BG:CV] Import %s not found in DB.", import_id)
            return

        raw_text = import_row.raw_text or ""
        if not raw_text:
            logger.error("[BG:CV] Import %s has no CV text to process.", import_id)
            mark_import_failed(import_row, "CV text is missing.")
            db.commit()
            return

        logger.info("[BG:CV] Step 1/2 — LLM extraction starting for import %s", import_id)
        try:
            extracted = extraction_svc.extract_cv(raw_text)
        except ExtractionError as exc:
            logger.error("[BG:CV] LLM extraction FAILED for import %s: %s", import_id, exc)
            mark_import_failed(import_row, str(exc))
            db.commit()
            return
        except Exception as exc:
            logger.exception("[BG:CV] Unexpected error during extraction for import %s: %s", import_id, exc)
            mark_import_failed(import_row, f"Unexpected extraction error: {exc}")
            db.commit()
            return

        email = normalize_email(extracted.email)
        if email is None:
            logger.error("[BG:CV] No valid email extracted for import %s", import_id)
            if not import_row.name and extracted.candidate_name:
                import_row.name = extracted.candidate_name
            mark_import_failed(import_row, "No valid email address found in the CV.")
            db.commit()
            return

        import_row.proposed_email = email
        import_row.extracted_data = extracted.model_dump()

        existing = db.query(Candidate).filter_by(email=email).first()
        if existing is not None:
            import_row.status = ImportStatus.CONFLICT
            import_row.existing_email = email
            db.commit()
            logger.info(
                "[BG:CV] Duplicate email detected — import_id=%s email=%s (awaiting user resolution)",
                import_id, email,
            )
            return

        candidate = create_candidate_from_extraction(
            db,
            email=email,
            extracted=extracted,
            raw_text=raw_text,
            source_name=import_row.source_name,
        )
        db.flush()

        logger.info(
            "[BG:CV] Candidate %s structured — name=%r  title=%r  role=%r  exp=%s yrs",
            email, extracted.candidate_name, extracted.current_title,
            extracted.normalized_role, extracted.years_experience,
        )

        logger.info("[BG:CV] Step 2/2 — Generating embedding for candidate %s", email)
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=email, entity_type="candidate")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        try:
            embedding_svc.generate_and_store(db, "candidate", email, extracted.summary)
            if log:
                log.status = ProcessingStatus.EMBEDDED
            delete_import_row(db, import_row)
            db.commit()
            logger.info("[BG:CV] Candidate %s fully processed — status→EMBEDDED  ✓", email)
        except Exception as exc:
            logger.error("[BG:CV] Embedding FAILED for candidate %s: %s", email, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Embedding error: {exc}"
            delete_import_row(db, import_row)
            db.commit()

    finally:
        db.close()
        logger.info("[BG:CV] Background task finished for import %s.", import_id)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=CandidateUploadResponse, status_code=202)
async def upload_candidate(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """
    Upload a candidate CV PDF.
    Returns immediately with an import_id. Processing happens asynchronously.
    Poll GET /candidates/imports or GET /candidates/{email} after processing completes.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    logger.info(
        "[API:CV] Upload received — filename=%r  size=%.1f KB",
        file.filename, len(file_bytes) / 1024,
    )

    try:
        raw_text = extract_pdf_text(file_bytes)
    except PDFExtractionError as exc:
        logger.error("[API:CV] PDF extraction failed for %r: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    import_row = create_import(
        db, raw_text=raw_text, source_name="local_kb", name=file.filename,
    )
    db.commit()

    background_tasks.add_task(_process_import, import_row.id, extraction_svc, embedding_svc)

    logger.info(
        "[API:CV] Import queued — import_id=%s  raw_text_chars=%d  background_task=queued",
        import_row.id, len(raw_text),
    )
    return CandidateUploadResponse(
        import_id=import_row.id,
        status=ImportStatus.PROCESSING,
        message="PDF received. Structured extraction is running in the background.",
    )


@router.get("/imports", response_model=list[CandidateImportResponse])
def list_imports(db: Session = Depends(get_db)) -> list[CandidateImportResponse]:
    """Return all candidate imports (processing, conflicts, failed)."""
    rows = (
        db.query(CandidateImport)
        .filter(CandidateImport.status != ImportStatus.COMPLETED)
        .filter(CandidateImport.status != ImportStatus.DISCARDED)
        .order_by(CandidateImport.created_at.desc())
        .all()
    )
    return [_import_response(row) for row in rows]


@router.get("/imports/conflicts", response_model=list[CandidateConflictResponse])
def list_conflicts(db: Session = Depends(get_db)) -> list[CandidateConflictResponse]:
    """Return imports where the email already exists — user must choose update or keep."""
    rows = (
        db.query(CandidateImport)
        .filter_by(status=ImportStatus.CONFLICT)
        .order_by(CandidateImport.created_at.desc())
        .all()
    )
    results: list[CandidateConflictResponse] = []
    for row in rows:
        if not row.proposed_email or not row.extracted_data:
            continue
        existing = db.query(Candidate).filter_by(email=row.proposed_email).first()
        if existing is None:
            continue
        results.append(
            CandidateConflictResponse(
                import_id=row.id,
                proposed_email=row.proposed_email,
                source_name=row.source_name,
                proposed=row.extracted_data,
                existing={
                    "email": existing.email,
                    "name": existing.name,
                    "current_title": existing.current_title,
                    "current_company": existing.current_company,
                    "location": existing.location,
                    "source_name": existing.source_name,
                    "summary": existing.summary,
                },
            )
        )
    return results


@router.post("/imports/{import_id}/resolve", response_model=CandidateResponse | dict)
def resolve_conflict(
    import_id: str,
    body: ResolveImportRequest,
    db: Session = Depends(get_db),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """Resolve a duplicate-email conflict by updating the existing record or keeping it."""
    import_row = db.query(CandidateImport).filter_by(id=import_id).first()
    if import_row is None:
        raise NotFoundError(message=f"Import {import_id!r} not found.")
    if import_row.status != ImportStatus.CONFLICT:
        raise HTTPException(status_code=409, detail=f"Import is not in CONFLICT status (current: {import_row.status}).")

    try:
        candidate = resolve_import_conflict(db, import_row, body.action, embedding_svc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if candidate is None:
        return {"import_id": import_id, "action": "keep", "message": "Existing candidate data kept."}

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=candidate.email, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING
    return _candidate_response(candidate, status)


@router.get("/imports/{import_id}", response_model=CandidateImportResponse)
def get_import(import_id: str, db: Session = Depends(get_db)) -> CandidateImportResponse:
    """Return a single candidate import by id."""
    row = db.query(CandidateImport).filter_by(id=import_id).first()
    if row is None:
        raise NotFoundError(message=f"Import {import_id!r} not found.")
    return _import_response(row)


@router.delete("/imports/{import_id}", status_code=204)
def dismiss_import(import_id: str, db: Session = Depends(get_db)) -> Response:
    """Remove a failed or conflict import notification from the UI."""
    row = db.query(CandidateImport).filter_by(id=import_id).first()
    if row is None:
        raise NotFoundError(message=f"Import {import_id!r} not found.")
    delete_import_row(db, row)
    db.commit()
    logger.info("[API:CV] Import dismissed — import_id=%s", import_id)
    return Response(status_code=204)


@router.get("", response_model=list[CandidateResponse])
def list_candidates(
    source_name: str | None = None,
    db: Session = Depends(get_db),
) -> list[CandidateResponse]:
    """Return all candidates, optionally filtered by source_name."""
    query = db.query(Candidate)
    if source_name:
        query = query.filter(Candidate.source_name == source_name)
    candidates = query.order_by(Candidate.created_at.desc()).all()

    results = []
    for candidate in candidates:
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=candidate.email, entity_type="candidate")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        proc_status = log.status if log else ProcessingStatus.PENDING
        results.append(_candidate_response(candidate, proc_status))
    return results


@router.get("/{candidate_email}", response_model=CandidateResponse)
def get_candidate(candidate_email: str, db: Session = Depends(get_db)):
    """Return the structured candidate record with its current processing status."""
    email = normalize_email(candidate_email) or candidate_email
    candidate = db.query(Candidate).filter_by(email=email).first()
    if candidate is None:
        raise NotFoundError(message=f"Candidate {candidate_email!r} not found.")

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=email, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING
    return _candidate_response(candidate, status)


@router.delete("/{candidate_email}", status_code=204)
def delete_candidate(candidate_email: str, db: Session = Depends(get_db)) -> Response:
    """Delete a candidate and all related match results, embeddings, and processing logs."""
    email = normalize_email(candidate_email) or candidate_email
    candidate = db.query(Candidate).filter_by(email=email).first()
    if candidate is None:
        raise NotFoundError(message=f"Candidate {candidate_email!r} not found.")

    db.query(MatchResult).filter_by(candidate_id=email).delete()
    db.query(Embedding).filter_by(entity_type="candidate", entity_id=email).delete()
    db.query(ProcessingLog).filter_by(entity_type="candidate", entity_id=email).delete()
    db.delete(candidate)
    db.commit()

    logger.info("[API:CV] Candidate deleted — email=%s", email)
    return Response(status_code=204)
