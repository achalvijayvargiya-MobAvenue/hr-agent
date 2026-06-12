"""
Job routes.

POST /jobs/upload   — accept a JD PDF, extract text, trigger background processing
GET  /jobs/{job_id} — return the structured job record with current processing status
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
from hr_agent.models.job import Job
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.schemas.job import HardChecksUpdate, JobResponse, JobUploadResponse
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.services.pdf_service import PDFExtractionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── Background task ────────────────────────────────────────────────────────────

def _process_job(
    job_id: str,
    raw_text: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """
    Background task: LLM extraction → DB update → embedding.
    Uses its own DB session (background tasks run outside the request scope).
    """
    from hr_agent.database import SessionLocal

    logger.info("[BG:JOB] Background processing started — job_id: %s", job_id)
    db = SessionLocal()
    try:
        log = db.query(ProcessingLog).filter_by(entity_id=job_id, entity_type="job").first()

        # ── Step 1: LLM extraction ─────────────────────────────────────────
        logger.info("[BG:JOB] Step 1/2 — LLM extraction starting for job %s", job_id)
        try:
            extracted = extraction_svc.extract_jd(raw_text)
        except ExtractionError as exc:
            logger.error("[BG:JOB] LLM extraction FAILED for job %s: %s", job_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = str(exc)
                db.commit()
            return
        except Exception as exc:
            logger.exception("[BG:JOB] Unexpected error during extraction for job %s: %s", job_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Unexpected extraction error: {exc}"
                db.commit()
            return

        job = db.query(Job).filter_by(id=job_id).first()
        if job is None:
            logger.error("[BG:JOB] Job %s not found in DB during background task.", job_id)
            return

        job.title = extracted.title
        job.normalized_role = extracted.normalized_role
        job.experience_min = extracted.experience_min
        job.experience_max = extracted.experience_max
        job.employment_type = extracted.employment_type
        job.location = extracted.location
        job.must_have_skills = extracted.must_have_skills
        job.good_to_have_skills = extracted.good_to_have_skills
        job.education_requirements = extracted.education_requirements
        job.certifications = extracted.certifications
        job.responsibilities = extracted.responsibilities
        job.tools_and_technologies = extracted.tools_and_technologies
        job.seniority_level = extracted.seniority_level
        job.department = extracted.department
        job.industry = extracted.industry
        job.summary = extracted.summary

        if log:
            log.status = ProcessingStatus.STRUCTURED
        db.commit()
        logger.info(
            "[BG:JOB] Job %s structured — title=%r  role=%r  exp=%s–%s  seniority=%r  "
            "must_have=%s  tools=%s  status→STRUCTURED",
            job_id, extracted.title, extracted.normalized_role,
            extracted.experience_min, extracted.experience_max,
            extracted.seniority_level, extracted.must_have_skills,
            extracted.tools_and_technologies,
        )

        # ── Step 2: Embedding ──────────────────────────────────────────────
        logger.info("[BG:JOB] Step 2/2 — Generating embedding for job %s", job_id)
        try:
            embedding_svc.generate_and_store(db, "job", job_id, extracted.summary)
            if log:
                log.status = ProcessingStatus.EMBEDDED
            db.commit()
            logger.info(
                "[BG:JOB] Job %s fully processed — status→EMBEDDED  ✓", job_id
            )
        except Exception as exc:
            logger.error("[BG:JOB] Embedding FAILED for job %s: %s", job_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Embedding error: {exc}"
                db.commit()

    finally:
        db.close()
        logger.info("[BG:JOB] Background task finished for job %s.", job_id)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=JobUploadResponse, status_code=202)
async def upload_job(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """
    Upload a job description PDF.
    Returns immediately with a job_id. Processing (LLM extraction + embedding)
    happens asynchronously. Poll GET /jobs/{job_id} to check status.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    logger.info(
        "[API:JOB] Upload received — filename=%r  size=%.1f KB",
        file.filename, len(file_bytes) / 1024,
    )

    try:
        raw_text = extract_pdf_text(file_bytes)
    except PDFExtractionError as exc:
        logger.error("[API:JOB] PDF extraction failed for %r: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = Job(raw_text=raw_text)
    db.add(job)
    db.flush()

    log = ProcessingLog(
        entity_type="job",
        entity_id=job.id,
        status=ProcessingStatus.EXTRACTED,
    )
    db.add(log)
    db.commit()

    background_tasks.add_task(_process_job, job.id, raw_text, extraction_svc, embedding_svc)

    logger.info(
        "[API:JOB] Job created — job_id=%s  raw_text_chars=%d  status=EXTRACTED  "
        "background_task=queued",
        job.id, len(raw_text),
    )
    return JobUploadResponse(
        job_id=job.id,
        status=ProcessingStatus.EXTRACTED,
        message="PDF received. Structured extraction is running in the background.",
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Return the structured job record with its current processing status."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=job_id, entity_type="job")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING

    return JobResponse(
        id=job.id,
        title=job.title,
        normalized_role=job.normalized_role,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        employment_type=job.employment_type,
        location=job.location,
        must_have_skills=job.must_have_skills or [],
        good_to_have_skills=job.good_to_have_skills or [],
        education_requirements=job.education_requirements or [],
        certifications=job.certifications or [],
        responsibilities=job.responsibilities or [],
        tools_and_technologies=job.tools_and_technologies or [],
        seniority_level=job.seniority_level,
        department=job.department,
        industry=job.industry,
        summary=job.summary,
        hard_checks=job.hard_checks,
        status=status,
        created_at=job.created_at,
    )


@router.put("/{job_id}/hard-checks", response_model=JobResponse)
def update_hard_checks(
    job_id: str,
    body: HardChecksUpdate,
    db: Session = Depends(get_db),
):
    """
    Save hard-check criteria for a job.
    On the next matching run, candidates that fail these checks are eliminated.
    Send an empty object {} to remove all hard checks.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    job.hard_checks = body.hard_checks or None
    db.commit()

    logger.info(
        "[API:JOB] Hard checks updated for job %s — checks: %s",
        job_id, body.hard_checks,
    )

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=job_id, entity_type="job")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING

    return JobResponse(
        id=job.id,
        title=job.title,
        normalized_role=job.normalized_role,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        employment_type=job.employment_type,
        location=job.location,
        must_have_skills=job.must_have_skills or [],
        good_to_have_skills=job.good_to_have_skills or [],
        education_requirements=job.education_requirements or [],
        certifications=job.certifications or [],
        responsibilities=job.responsibilities or [],
        tools_and_technologies=job.tools_and_technologies or [],
        seniority_level=job.seniority_level,
        department=job.department,
        industry=job.industry,
        summary=job.summary,
        hard_checks=job.hard_checks,
        status=status,
        created_at=job.created_at,
    )
