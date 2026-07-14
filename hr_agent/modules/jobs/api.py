"""
Job routes.

POST /jobs/upload   — accept a JD PDF, extract text, trigger background processing
GET  /jobs/{job_id} — return the structured job record with current processing status
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from hr_agent.core.deps import (
    extract_pdf_text,
    get_current_user,
    get_db,
    get_domain_classification_service,
    get_embedding_service,
    get_extraction_service,
    get_pool_service,
)
from hr_agent.core.errors import ConflictError, NotFoundError
from hr_agent.core.models.embedding import Embedding
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.matching.models import MatchResult
from hr_agent.modules.matching.pool_models import JobCandidatePool
from hr_agent.core.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.modules.users.models import User
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.taxonomy.schemas import DomainUpdate, PoolBuildResponse, PoolEntryResponse, PoolMemberUpdate
from hr_agent.modules.jobs.schemas import (
    HardChecksUpdate,
    JobResponse,
    JobUploadResponse,
    PositionApprove,
    PositionManualCreate,
    PositionUpdate,
)
from hr_agent.modules.taxonomy.classification_service import (
    DomainClassificationError,
    DomainClassificationService,
    apply_domain_to_job,
    apply_manual_domain,
)
from hr_agent.modules.taxonomy.domain_helpers import job_domain_dict
from hr_agent.core.services.embedding_service import EmbeddingService
from hr_agent.core.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.modules.matching.pool_service import PoolService
from hr_agent.modules.matching.profile_fingerprint_service import build_job_fingerprint
from hr_agent.core.services.pdf_service import PDFExtractionError

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
        salary=job.salary,
        **job_domain_dict(job),
        hard_checks=job.hard_checks,
        candidates_required=job.candidates_required,
        position_status=job.position_status,
        created_by=job.created_by,
        status=_job_proc_status(db, job.id),
        created_at=job.created_at,
    )


def _pool_entry_response(row: JobCandidatePool, candidate: Candidate | None) -> PoolEntryResponse:
    return PoolEntryResponse(
        candidate_id=row.candidate_id,
        candidate_name=candidate.name if candidate else None,
        current_title=candidate.current_title if candidate else None,
        domain_code=candidate.domain_code if candidate else None,
        subdomain_codes=candidate.subdomain_codes or [] if candidate else [],
        pool_status=row.pool_status,  # type: ignore[arg-type]
        domain_match_score=row.domain_match_score,
        subdomain_match_score=row.subdomain_match_score,
        relevance_score=row.relevance_score,
        match_reason=row.match_reason,
        computed_at=row.computed_at,
    )


def _pool_build_response(job_id: str, rows: list[JobCandidatePool], db: Session) -> PoolBuildResponse:
    cand_ids = [r.candidate_id for r in rows]
    candidates = db.query(Candidate).filter(Candidate.email.in_(cand_ids)).all() if cand_ids else []
    cand_map = {c.email: c for c in candidates}
    entries = [_pool_entry_response(r, cand_map.get(r.candidate_id)) for r in rows]
    computed_at = max((r.computed_at for r in rows), default=datetime.now(timezone.utc))
    in_pool = sum(1 for r in rows if r.pool_status in ("in_pool", "manual_add"))
    return PoolBuildResponse(
        job_id=job_id,
        total_candidates=len(rows),
        in_pool=in_pool,
        out_of_pool=sum(1 for r in rows if r.pool_status == "out_of_pool"),
        manual_add=sum(1 for r in rows if r.pool_status == "manual_add"),
        manual_exclude=sum(1 for r in rows if r.pool_status == "manual_exclude"),
        computed_at=computed_at,
        entries=sorted(entries, key=lambda e: e.relevance_score, reverse=True),
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
    if body.salary is not None:
        job.salary = body.salary
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
    from hr_agent.core.database import SessionLocal

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

        job.title = extracted.title or job.title
        job.normalized_role = extracted.normalized_role or job.normalized_role
        job.experience_min = extracted.experience_min if extracted.experience_min is not None else job.experience_min
        job.experience_max = extracted.experience_max if extracted.experience_max is not None else job.experience_max
        job.employment_type = extracted.employment_type or job.employment_type
        job.location = extracted.location or job.location
        job.must_have_skills = extracted.must_have_skills if extracted.must_have_skills else job.must_have_skills
        job.good_to_have_skills = extracted.good_to_have_skills if extracted.good_to_have_skills else job.good_to_have_skills
        job.education_requirements = extracted.education_requirements if extracted.education_requirements else job.education_requirements
        job.certifications = extracted.certifications if extracted.certifications else job.certifications
        job.responsibilities = extracted.responsibilities if extracted.responsibilities else job.responsibilities
        job.tools_and_technologies = extracted.tools_and_technologies if extracted.tools_and_technologies else job.tools_and_technologies
        job.seniority_level = extracted.seniority_level or job.seniority_level
        job.department = extracted.department or job.department
        job.industry = extracted.industry or job.industry
        job.summary = extracted.summary or job.summary

        # ── Step 1b: Domain classification ───────────────────────────────────
        logger.info("[BG:JOB] Step 1b — Domain classification for job %s", job_id)
        try:
            from hr_agent.core.deps import get_domain_classification_service

            domain_svc = get_domain_classification_service()
            classification = domain_svc.classify_job(
                title=extracted.title,
                normalized_role=extracted.normalized_role,
                seniority_level=extracted.seniority_level,
                department=extracted.department,
                industry=extracted.industry,
                skills=extracted.must_have_skills + extracted.good_to_have_skills,
                tools=extracted.tools_and_technologies,
                responsibilities=extracted.responsibilities,
                education=extracted.education_requirements,
                summary=extracted.summary,
            )
            apply_domain_to_job(job, classification)
        except DomainClassificationError as exc:
            logger.warning("[BG:JOB] Domain classification failed for job %s: %s", job_id, exc)
        except Exception as exc:
            logger.warning("[BG:JOB] Unexpected domain classification error for job %s: %s", job_id, exc)

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
            embedding_svc.ensure_fingerprint_embedding(
                db, "job", job_id, build_job_fingerprint(job)
            )
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

def _process_manual_job(
    job_id: str,
    embedding_svc: EmbeddingService,
) -> None:
    """
    Background task for manually created positions: Domain classification → Embedding.
    """
    from hr_agent.core.database import SessionLocal

    logger.info("[BG:JOB] Manual processing started — job_id: %s", job_id)
    db = SessionLocal()
    try:
        log = db.query(ProcessingLog).filter_by(entity_id=job_id, entity_type="job").first()
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return

        # ── Step 1b: Domain classification ───────────────────────────────────
        logger.info("[BG:JOB] Step 1b — Domain classification for manual job %s", job_id)
        try:
            from hr_agent.core.deps import get_domain_classification_service

            domain_svc = get_domain_classification_service()
            classification = domain_svc.classify_job(
                title=job.title,
                normalized_role=job.normalized_role,
                seniority_level=job.seniority_level,
                department=job.department,
                industry=job.industry,
                skills=(job.must_have_skills or []) + (job.good_to_have_skills or []),
                tools=job.tools_and_technologies,
                responsibilities=job.responsibilities,
                education=job.education_requirements,
                summary=job.summary,
            )
            from hr_agent.modules.taxonomy.classification_service import apply_domain_to_job
            apply_domain_to_job(job, classification)
        except Exception as exc:
            logger.warning("[BG:JOB] Domain classification failed for manual job %s: %s", job_id, exc)

        # ── Step 2: Embedding ──────────────────────────────────────────────
        logger.info("[BG:JOB] Step 2/2 — Generating embedding for manual job %s", job_id)
        try:
            embedding_svc.generate_and_store(db, "job", job_id, job.summary or job.title or "")
            from hr_agent.modules.matching.profile_fingerprint_service import build_job_fingerprint
            embedding_svc.ensure_fingerprint_embedding(
                db, "job", job_id, build_job_fingerprint(job)
            )
            if log:
                log.status = ProcessingStatus.EMBEDDED
            db.commit()
            logger.info(
                "[BG:JOB] Manual job %s fully processed — status→EMBEDDED  ✓", job_id
            )
        except Exception as exc:
            logger.error("[BG:JOB] Embedding FAILED for manual job %s: %s", job_id, exc)
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = f"Embedding error: {exc}"
                db.commit()

    finally:
        db.close()
        logger.info("[BG:JOB] Manual background task finished for job %s.", job_id)


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
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
        certifications=body.certifications,
        responsibilities=body.responsibilities,
        summary=body.summary,
        salary=body.salary,
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

    background_tasks.add_task(_process_manual_job, job.id, embedding_svc)

    logger.info(
        "[API:JOB] Manual position created — job_id=%s  title=%r  created_by=%s",
        job.id, job.title, current_user.id,
    )

    return _job_to_response(job, db)


@router.post("/sync-zoho", response_model=dict, status_code=200)
def sync_zoho_jobs(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """Fetch active jobs from Zoho Recruit, map to DB, and trigger AI extraction."""
    from hr_agent.modules.integrations.zoho.client import ZohoRecruitClient
    zoho = ZohoRecruitClient()
    jobs = zoho.get_active_jobs()
    
    added_count = 0
    updated_count = 0
    added_titles = []
    updated_titles = []
    
    for zjob in jobs:
        zoho_id = zjob.get("id")
        title = zjob.get("Posting_Title")
        
        if not zoho_id or not title:
            continue
            
        exp = zjob.get("Work_Experience_in_years") or zjob.get("Work_Experience")
        exp_min, exp_max = None, None
        if exp and isinstance(exp, str):
            parts = exp.split("-")
            if len(parts) == 2:
                try:
                    exp_min = int(parts[0].strip())
                    exp_max = int(parts[1].strip().split()[0])
                except ValueError:
                    pass
            elif exp.isdigit():
                exp_min = int(exp)
        elif exp and isinstance(exp, int):
            exp_min = exp
            
        status = zjob.get("Job_Opening_Status")
        pos_status = "OPEN"
        if status:
            if "closed" in status.lower() or "filled" in status.lower() or "cancelled" in status.lower():
                pos_status = "CLOSED"
            elif "draft" in status.lower():
                pos_status = "DRAFT"
        
        candidates_req = None
        try:
            if zjob.get("Number_of_Positions"):
                candidates_req = int(zjob.get("Number_of_Positions"))
        except (ValueError, TypeError):
            pass
            
        raw_text_parts = [
            f"Title: {title}",
            f"Department: {zjob.get('Department', '')}",
            f"Location: {zjob.get('City', '')} {zjob.get('State', '')}",
            f"Type: {zjob.get('Job_Type', '')}",
            f"Experience: {exp}",
            f"Description:\n{zjob.get('Job_Description', '')}"
        ]
        full_text = "\n".join(p for p in raw_text_parts if p.strip())
        
        # Normalize employment type
        emp_type = zjob.get("Job_Type")
        if emp_type:
            emp_type_lower = emp_type.lower()
            if "full" in emp_type_lower and "time" in emp_type_lower:
                emp_type = "Full-time"
            elif "part" in emp_type_lower and "time" in emp_type_lower:
                emp_type = "Part-time"
                
        loc = zjob.get("City") or zjob.get("State")
        if zjob.get("City") and zjob.get("State"):
            loc = f"{zjob.get('City')}, {zjob.get('State')}"

        existing = db.query(Job).filter_by(zoho_id=zoho_id).first()
        if existing:
            def norm(v):
                return str(v).strip() if v is not None else ""
                
            old_zjob = existing.zoho_data or {}
            changed = False
            desc_changed = norm(old_zjob.get("Job_Description")) != norm(zjob.get("Job_Description"))
            
            if norm(old_zjob.get("Posting_Title")) != norm(title):
                existing.title = title
                changed = True
                
            if norm(old_zjob.get("Department")) != norm(zjob.get("Department")):
                existing.department = zjob.get("Department")
                changed = True
                
            if norm(old_zjob.get("Industry")) != norm(zjob.get("Industry")):
                existing.industry = zjob.get("Industry")
                changed = True
                
            if norm(old_zjob.get("City")) != norm(zjob.get("City")) or norm(old_zjob.get("State")) != norm(zjob.get("State")):
                existing.location = loc
                changed = True
                
            if norm(old_zjob.get("Job_Type")) != norm(zjob.get("Job_Type")):
                existing.employment_type = emp_type
                changed = True
                
            old_exp = old_zjob.get("Work_Experience_in_years") or old_zjob.get("Work_Experience")
            new_exp = zjob.get("Work_Experience_in_years") or zjob.get("Work_Experience")
            if norm(old_exp) != norm(new_exp):
                existing.experience_min = exp_min
                existing.experience_max = exp_max
                changed = True
                
            if norm(old_zjob.get("Number_of_Positions")) != norm(zjob.get("Number_of_Positions")):
                existing.candidates_required = candidates_req
                changed = True
                
            if desc_changed:
                existing.summary = zjob.get("Job_Description")
                existing.raw_text = full_text
                changed = True
                
            if norm(old_zjob.get("Salary")) != norm(zjob.get("Salary")):
                existing.salary = str(zjob.get("Salary")) if zjob.get("Salary") else None
                changed = True
                
            if norm(old_zjob.get("Job_Opening_Status")) != norm(zjob.get("Job_Opening_Status")):
                existing.position_status = pos_status
                changed = True

            if changed:
                existing.zoho_data = zjob
                db.commit()
                db.refresh(existing)
                
                if desc_changed and existing.raw_text:
                    background_tasks.add_task(_process_job, existing.id, existing.raw_text, extraction_svc, embedding_svc)
                    
                updated_count += 1
                updated_titles.append(title)
                
            continue

        new_job = Job(
            title=title,
            department=zjob.get("Department"),
            industry=zjob.get("Industry"),
            location=loc,
            employment_type=emp_type,
            experience_min=exp_min,
            experience_max=exp_max,
            candidates_required=candidates_req,
            summary=zjob.get("Job_Description"),
            salary=str(zjob.get("Salary")) if zjob.get("Salary") else None,
            position_status=pos_status,
            created_by=current_user.id,
            zoho_id=zoho_id,
            zoho_data=zjob,
            raw_text=full_text,
        )
        db.add(new_job)
        db.flush()
        
        log = ProcessingLog(
            entity_type="job",
            entity_id=new_job.id,
            status=ProcessingStatus.EXTRACTED,
        )
        db.add(log)
        db.commit()
        db.refresh(new_job)
        
        if new_job.raw_text:
            background_tasks.add_task(_process_job, new_job.id, new_job.raw_text, extraction_svc, embedding_svc)
        
        added_count += 1
        added_titles.append(title)
        
    return {
        "message": f"Successfully synced jobs from Zoho",
        "added": added_count,
        "updated": updated_count,
        "added_titles": added_titles,
        "updated_titles": updated_titles
    }


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
    return [_job_to_response(job, db) for job in jobs]


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
    db.query(JobCandidatePool).filter_by(job_id=job_id).delete()
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

    return _job_to_response(job, db)


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

    return _job_to_response(job, db)


# ── Domain & pool (Phase 1–2) ─────────────────────────────────────────────────


@router.post("/{job_id}/classify-domain", response_model=JobResponse)
def classify_job_domain(
    job_id: str,
    db: Session = Depends(get_db),
    domain_svc: DomainClassificationService = Depends(get_domain_classification_service),
) -> JobResponse:
    """Re-run LLM domain/subdomain classification from current job fields."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")
    if not job.normalized_role:
        raise HTTPException(status_code=422, detail="Job must be structured before domain classification.")

    try:
        classification = domain_svc.classify_job(
            title=job.title,
            normalized_role=job.normalized_role,
            seniority_level=job.seniority_level,
            department=job.department,
            industry=job.industry,
            skills=(job.must_have_skills or []) + (job.good_to_have_skills or []),
            tools=job.tools_and_technologies,
            responsibilities=job.responsibilities,
            education=job.education_requirements,
            summary=job.summary,
        )
        apply_domain_to_job(job, classification)
        db.commit()
        db.refresh(job)
    except DomainClassificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _job_to_response(job, db)


@router.put("/{job_id}/domain", response_model=JobResponse)
def update_job_domain(job_id: str, body: DomainUpdate, db: Session = Depends(get_db)) -> JobResponse:
    """Manually set domain and subdomains from the taxonomy."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")
    try:
        apply_manual_domain(job, body.domain_code, body.subdomain_codes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(job)
    return _job_to_response(job, db)


@router.get("/{job_id}/pool", response_model=PoolBuildResponse)
def get_job_pool(
    job_id: str,
    db: Session = Depends(get_db),
    pool_svc: PoolService = Depends(get_pool_service),
) -> PoolBuildResponse:
    """Return the current candidate pool for a job (build first if empty)."""
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise NotFoundError(message=f"Job {job_id!r} not found.")

    rows = pool_svc.get_pool(db, job_id)
    if not rows and job.domain_code:
        rows = pool_svc.build_pool(db, job_id)
    return _pool_build_response(job_id, rows, db)


@router.post("/{job_id}/pool/build", response_model=PoolBuildResponse)
def build_job_pool(
    job_id: str,
    db: Session = Depends(get_db),
    pool_svc: PoolService = Depends(get_pool_service),
) -> PoolBuildResponse:
    """Rebuild the candidate pool from domain/subdomain taxonomy rules."""
    try:
        rows = pool_svc.build_pool(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _pool_build_response(job_id, rows, db)


@router.put("/{job_id}/pool/{candidate_id}", response_model=PoolEntryResponse)
def update_pool_member(
    job_id: str,
    candidate_id: str,
    body: PoolMemberUpdate,
    db: Session = Depends(get_db),
    pool_svc: PoolService = Depends(get_pool_service),
) -> PoolEntryResponse:
    """Manually add, exclude, or reset a candidate in the job pool."""
    try:
        row = pool_svc.set_member_status(db, job_id, candidate_id, body.pool_status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    candidate = db.query(Candidate).filter_by(email=candidate_id).first()
    return _pool_entry_response(row, candidate)
