"""
Candidate routes.

POST /candidates/upload   — accept a CV PDF, extract text, trigger background processing
GET  /candidates/{id}     — return the structured candidate record with current status
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from hr_agent.api.deps import (
    extract_pdf_text,
    get_db,
    get_embedding_service,
    get_extraction_service,
)
from hr_agent.models.candidate import Candidate
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.schemas.candidate import CandidateResponse, CandidateUploadResponse
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.services.pdf_service import PDFExtractionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])


# ── Background task ────────────────────────────────────────────────────────────

def _process_candidate(
    candidate_id: str,
    raw_text: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """Background task: LLM extraction → DB update → embedding."""
    from hr_agent.database import SessionLocal

    logger.info("[BG:CV] Background processing started — candidate_id: %s", candidate_id)
    db = SessionLocal()
    try:
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=candidate_id, entity_type="candidate")
            .first()
        )

        # ── Step 1: LLM extraction ─────────────────────────────────────────
        logger.info("[BG:CV] Step 1/2 — LLM extraction starting for candidate %s", candidate_id)
        try:
            extracted = extraction_svc.extract_cv(raw_text)
        except ExtractionError as exc:
            logger.error("[BG:CV] LLM extraction FAILED for candidate %s: %s", candidate_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = str(exc)
                db.commit()
            return
        except Exception as exc:
            logger.exception("[BG:CV] Unexpected error during extraction for candidate %s: %s", candidate_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Unexpected extraction error: {exc}"
                db.commit()
            return

        candidate = db.query(Candidate).filter_by(id=candidate_id).first()
        if candidate is None:
            logger.error("[BG:CV] Candidate %s not found in DB during background task.", candidate_id)
            return

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

        if log:
            log.status = ProcessingStatus.STRUCTURED
        db.commit()
        logger.info(
            "[BG:CV] Candidate %s structured — name=%r  title=%r  role=%r  exp=%s yrs  "
            "seniority=%r  skills=%s (%d)  tools=%s  status→STRUCTURED",
            candidate_id, extracted.candidate_name, extracted.current_title,
            extracted.normalized_role, extracted.years_experience,
            extracted.seniority_level, extracted.skills[:4], len(extracted.skills),
            extracted.tools_and_technologies[:3],
        )

        # ── Step 2: Embedding ──────────────────────────────────────────────
        logger.info("[BG:CV] Step 2/2 — Generating embedding for candidate %s", candidate_id)
        try:
            embedding_svc.generate_and_store(db, "candidate", candidate_id, extracted.summary)
            if log:
                log.status = ProcessingStatus.EMBEDDED
            db.commit()
            logger.info(
                "[BG:CV] Candidate %s fully processed — status→EMBEDDED  ✓", candidate_id
            )
        except Exception as exc:
            logger.error("[BG:CV] Embedding FAILED for candidate %s: %s", candidate_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Embedding error: {exc}"
                db.commit()

    finally:
        db.close()
        logger.info("[BG:CV] Background task finished for candidate %s.", candidate_id)


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
    Returns immediately with a candidate_id. Processing happens asynchronously.
    Poll GET /candidates/{id} to check status.
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

    candidate = Candidate(raw_text=raw_text)
    db.add(candidate)
    db.flush()

    log = ProcessingLog(
        entity_type="candidate",
        entity_id=candidate.id,
        status=ProcessingStatus.EXTRACTED,
    )
    db.add(log)
    db.commit()

    background_tasks.add_task(
        _process_candidate, candidate.id, raw_text, extraction_svc, embedding_svc
    )

    logger.info(
        "[API:CV] Candidate created — candidate_id=%s  raw_text_chars=%d  "
        "status=EXTRACTED  background_task=queued",
        candidate.id, len(raw_text),
    )
    return CandidateUploadResponse(
        candidate_id=candidate.id,
        status=ProcessingStatus.EXTRACTED,
        message="PDF received. Structured extraction is running in the background.",
    )


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    """Return the structured candidate record with its current processing status."""
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found.")

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=candidate_id, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING

    return CandidateResponse(
        id=candidate.id,
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
        status=status,
        created_at=candidate.created_at,
    )
