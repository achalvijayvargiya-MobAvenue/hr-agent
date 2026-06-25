"""
Job routes.

POST /jobs/upload   — accept a JD PDF, extract text, trigger background processing
GET  /jobs/{job_id} — return the structured job record with current processing status
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
from hr_agent.core.errors import ConflictError, NotFoundError
from hr_agent.models.embedding import Embedding
from hr_agent.models.job import Job
from hr_agent.models.match_result import MatchResult
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.models.user import User
from hr_agent.schemas.job import (
    HardChecksUpdate,
    JobResponse,
    JobUploadResponse,
    PositionApprove,
    PositionManualCreate,
    PositionUpdate,
)
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.services.pdf_service import PDFExtractionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


def _job_proc_status(db: Session, job_id: str) -> str:
    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=job_id, entity_type="job")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    return log.status if log else ProcessingStatus.PENDING


def _job_to_response(job: Job, db: Session) -> JobResponse:
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
        candidates_required=job.candidates_required,
        position_status=job.position_status,
        created_by=job.created_by,
        status=_job_proc_status(db, job.id),
        created_at=job.created_at,
    )


def _apply_position_fields(job: Job, body: PositionApprove | PositionUpdate) -> None:
    if body.title is not None:
        job.title = body.title
    if body.normalized_role is not None:
        job.normalized_role = body.normalized_role
    if body.department is not None:
        job.department = body.department
    if body.industry is not None:
        job.industry = body.industry
    if body.location is not None:
        job.location = body.location
    if body.employment_type is not None:
        job.employment_type = body.employment_type
    if body.seniority_level is not None:
        job.seniority_level = body.seniority_level
    if body.experience_min is not None:
        job.experience_min = body.experience_min
    if body.experience_max is not None:
        job.experience_max = body.experience_max
    if body.candidates_required is not None:
        job.candidates_required = body.candidates_required
    if body.must_have_skills is not None:
        job.must_have_skills = body.must_have_skills
    if body.good_to_have_skills is not None:
        job.good_to_have_skills = body.good_to_have_skills
    if body.tools_and_technologies is not None:
        job.tools_and_technologies = body.tools_and_technologies
    if body.education_requirements is not None:
        job.education_requirements = body.education_requirements
    if body.certifications is not None:
        job.certifications = body.certifications
    if body.responsibilities is not None:
        job.responsibilities = body.responsibilities
    if body.summary is not None:
        job.summary = body.summary
    if body.hard_checks is not None:
        job.hard_checks = body.hard_checks
    if isinstance(body, PositionUpdate) and body.position_status is not None:
        job.position_status = body.position_status


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

        job.position_status = "DRAFT"
        if log:
            log.status = ProcessingStatus.STRUCTURED
        db.commit()
        logger.info(
            "[BG:JOB] Job %s structured — title=%r  role=%r  exp=%s–%s  seniority=%r  "
            "must_have=%s  tools=%s  status→STRUCTURED  position_status→DRAFT",
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


@router.post("/manual", response_model=JobResponse, status_code=201)
def create_manual_position(
    body: PositionManualCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """
    Create a new Open Position by filling in fields manually.
    The position starts in DRAFT status and is immediately marked as STRUCTURED
    (no LLM extraction needed).
    """
    job = Job(
        title=body.title,
        normalized_role=body.normalized_role,
        department=body.department,
        industry=body.industry,
        location=body.location,
        employment_type=body.employment_type,
        seniority_level=body.seniority_level,
        experience_min=body.experience_min,
        experience_max=body.experience_max,
        candidates_required=body.candidates_required,
        must_have_skills=body.must_have_skills or [],
        good_to_have_skills=body.good_to_have_skills or [],
        tools_and_technologies=body.tools_and_technologies or [],
        education_requirements=body.education_requirements or [],
        certifications=body.certifications or [],
        responsibilities=body.responsibilities or [],
        summary=body.summary,
        position_status="DRAFT",
        created_by=current_user.id,
    )
    db.add(job)
    db.flush()

    log = ProcessingLog(
        entity_type="job",
        entity_id=job.id,
        status=ProcessingStatus.STRUCTURED,
    )
    db.add(log)
    db.commit()
    db.refresh(job)

    logger.info(
        "[API:JOB] Manual position created — job_id=%s  title=%r  created_by=%s",
        job.id, job.title, current_user.id,
    )

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
        candidates_required=job.candidates_required,
        position_status=job.position_status,
        created_by=job.created_by,
        status=ProcessingStatus.STRUCTURED,
        created_at=job.created_at,
    )


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: str | None = None,
    created_by: str | None = None,
    db: Session = Depends(get_db),
) -> list[JobResponse]:
    """List all positions, optionally filtered by position_status or created_by."""
    query = db.query(Job)
    if status is not None:
        query = query.filter(Job.position_status == status)
    if created_by is not None:
        query = query.filter(Job.created_by == created_by)
    jobs = query.order_by(Job.created_at.desc()).all()

    results = []
    for job in jobs:
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=job.id, entity_type="job")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        proc_status = log.status if log else ProcessingStatus.PENDING
        results.append(JobResponse(
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
            candidates_required=job.candidates_required,
            position_status=job.position_status,
            created_by=job.created_by,
            status=proc_status,
            created_at=job.created_at,
        ))
    return results


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Return the structured job record with its current processing status."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")
    return _job_to_response(job, db)


@router.put("/{job_id}", response_model=JobResponse)
def update_position(
    job_id: str,
    body: PositionUpdate,
    db: Session = Depends(get_db),
) -> JobResponse:
    """
    Update an existing position. Any non-None fields in the body overwrite stored values.
    Supports editing all extracted fields, candidates_required, and position_status.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")

    _apply_position_fields(job, body)
    db.commit()
    db.refresh(job)

    logger.info(
        "[API:JOB] Position updated — job_id=%s  position_status=%s",
        job_id, job.position_status,
    )
    return _job_to_response(job, db)


@router.delete("/{job_id}", status_code=204)
def delete_position(job_id: str, db: Session = Depends(get_db)) -> Response:
    """Delete a position and all related match results, embeddings, and processing logs."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")

    db.query(MatchResult).filter_by(job_id=job_id).delete()
    db.query(Embedding).filter_by(entity_type="job", entity_id=job_id).delete()
    db.query(ProcessingLog).filter_by(entity_type="job", entity_id=job_id).delete()
    db.delete(job)
    db.commit()

    logger.info("[API:JOB] Position deleted — job_id=%s", job_id)
    return Response(status_code=204)


@router.put("/{job_id}/hard-checks", response_model=JobResponse)
def update_hard_checks(job_id: str, body: HardChecksUpdate, db: Session = Depends(get_db)):
    """
    Save hard-check criteria for a job.
    On the next matching run, candidates that fail these checks are eliminated.
    Send an empty object {} to remove all hard checks.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")

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
        candidates_required=job.candidates_required,
        position_status=job.position_status,
        created_by=job.created_by,
        status=status,
        created_at=job.created_at,
    )


@router.post("/{job_id}/approve", response_model=JobResponse)
def approve_position(
    job_id: str,
    body: PositionApprove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """
    Review and approve a DRAFT position, promoting it to OPEN.
    Any non-None fields in the request body overwrite the stored values.
    Returns 409 if the position is already OPEN or CLOSED.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")

    if job.position_status in ("OPEN", "CLOSED"):
        raise ConflictError(
            message=f"Position is already {job.position_status} and cannot be re-approved.",
        )

    # Apply any overriding edits from the body
    if body.title is not None:
        job.title = body.title
    if body.normalized_role is not None:
        job.normalized_role = body.normalized_role
    if body.department is not None:
        job.department = body.department
    if body.industry is not None:
        job.industry = body.industry
    if body.location is not None:
        job.location = body.location
    if body.employment_type is not None:
        job.employment_type = body.employment_type
    if body.seniority_level is not None:
        job.seniority_level = body.seniority_level
    if body.experience_min is not None:
        job.experience_min = body.experience_min
    if body.experience_max is not None:
        job.experience_max = body.experience_max
    if body.candidates_required is not None:
        job.candidates_required = body.candidates_required
    if body.must_have_skills is not None:
        job.must_have_skills = body.must_have_skills
    if body.good_to_have_skills is not None:
        job.good_to_have_skills = body.good_to_have_skills
    if body.tools_and_technologies is not None:
        job.tools_and_technologies = body.tools_and_technologies
    if body.education_requirements is not None:
        job.education_requirements = body.education_requirements
    if body.certifications is not None:
        job.certifications = body.certifications
    if body.responsibilities is not None:
        job.responsibilities = body.responsibilities
    if body.summary is not None:
        job.summary = body.summary
    if body.hard_checks is not None:
        job.hard_checks = body.hard_checks

    job.position_status = "OPEN"

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=job_id, entity_type="job")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    if log and log.status in (ProcessingStatus.EXTRACTED, ProcessingStatus.PENDING):
        log.status = ProcessingStatus.STRUCTURED

    db.commit()
    db.refresh(job)

    proc_status = log.status if log else ProcessingStatus.STRUCTURED
    logger.info(
        "[API:JOB] Position approved — job_id=%s  approved_by=%s  position_status→OPEN",
        job_id, current_user.id,
    )

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
        candidates_required=job.candidates_required,
        position_status=job.position_status,
        created_by=job.created_by,
        status=proc_status,
        created_at=job.created_at,
    )
