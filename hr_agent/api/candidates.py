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
    get_domain_classification_service,
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
    SyncZohoRequest,
    ZohoFormImportRequest,
)
from hr_agent.schemas.domain import DomainUpdate
from hr_agent.services.candidate_service import (
    create_candidate_from_extraction,
    create_import,
    delete_import_row,
    mark_import_failed,
    normalize_email,
    resolve_import_conflict,
    create_candidate_from_zoho_merge,
)
from hr_agent.services.domain_classification_service import (
    DomainClassificationError,
    DomainClassificationService,
    apply_domain_to_candidate,
    apply_manual_domain,
)
from hr_agent.services.domain_helpers import candidate_domain_dict
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionError, ExtractionService
from hr_agent.services.profile_fingerprint_service import build_candidate_fingerprint
from hr_agent.services.zoho.forms_client import ZohoFormsClient
from hr_agent.services.candidate_merge_service import CandidateMergeService, ZohoFormData, MergeStrategy

from hr_agent.services.zoho.client import ZohoRecruitClient

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
        **candidate_domain_dict(candidate),
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

        # ── Fallback: derive required fields the LLM may have left null ───────
        if not extracted.normalized_role:
            extracted.normalized_role = extracted.current_title or "Professional"
            logger.info(
                "[BG:CV] normalized_role was null — derived from title: %r",
                extracted.normalized_role,
            )
        if not extracted.candidate_name:
            extracted.candidate_name = import_row.name or "Unknown"
        if not extracted.summary:
            parts = []
            if extracted.candidate_name:
                parts.append(extracted.candidate_name)
            if extracted.current_title:
                parts.append(f"works as {extracted.current_title}")
            if extracted.current_company:
                parts.append(f"at {extracted.current_company}")
            if extracted.years_experience is not None:
                parts.append(f"with {extracted.years_experience} years of experience")
            if extracted.skills:
                parts.append(f"skilled in {', '.join(extracted.skills[:5])}")
            extracted.summary = " ".join(parts) + "." if parts else "Professional profile."
            logger.info("[BG:CV] summary was null — auto-generated from extracted fields.")
        # ─────────────────────────────────────────────────────────────────────

        import_row.proposed_email = email
        import_row.extracted_data = extracted.model_dump()

        existing = db.query(Candidate).filter_by(email=email).first()
        if existing is not None:
            # For Zoho candidates re-synced, UPDATE them instead of flagging as conflict
            if import_row.source_name == "zoho":
                logger.info(
                    "[BG:CV] Zoho re-import — updating existing candidate %s with LLM data.", email
                )
                from hr_agent.services.candidate_service import apply_extraction_to_candidate
                apply_extraction_to_candidate(existing, extracted)
                existing.raw_text = raw_text
                existing.source_name = "zoho"
                db.flush()
                candidate = existing
                # Skip to embedding
                import_row.proposed_email = email
            else:
                import_row.status = ImportStatus.CONFLICT
                import_row.existing_email = email
                db.commit()
                logger.info(
                    "[BG:CV] Duplicate email detected — import_id=%s email=%s (awaiting user resolution)",
                    import_id, email,
                )
                return
        else:
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

        logger.info("[BG:CV] Step 1b — Domain classification for candidate %s", email)
        try:
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
            db.flush()
        except DomainClassificationError as exc:
            logger.warning("[BG:CV] Domain classification failed for %s: %s", email, exc)
        except Exception as exc:
            logger.warning("[BG:CV] Unexpected domain classification error for %s: %s", email, exc)

        logger.info("[BG:CV] Step 2/2 — Generating embedding for candidate %s", email)
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=email, entity_type="candidate")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        try:
            embedding_svc.generate_and_store(db, "candidate", email, extracted.summary or raw_text)
            embedding_svc.ensure_fingerprint_embedding(
                db, "candidate", email, build_candidate_fingerprint(candidate)
            )
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


@router.get("/zoho/jobs")
def get_zoho_jobs():
    """Fetch active job openings from Zoho."""
    try:
        zoho_client = ZohoRecruitClient()
        jobs = zoho_client.get_active_jobs()
        return jobs
    except Exception as e:
        logger.error(f"[API:ZOHO] Failed to fetch jobs from Zoho: {e}")
        raise HTTPException(status_code=503, detail="Failed to connect to Zoho Recruit")

@router.get("/test-zoho-apps/{job_id}")
def test_zoho_apps(job_id: str):
    zoho_client = ZohoRecruitClient()
    results = {}
    
    # 1. Job_Openings
    url1 = f"{zoho_client.base_url}/Job_Openings/{job_id}/Candidates"
    r1 = zoho_client.session.get(url1, headers=zoho_client._get_headers())
    results["Job_Openings"] = {"status": r1.status_code, "text": r1.text[:200]}

    # 2. JobOpenings
    url2 = f"{zoho_client.base_url}/JobOpenings/{job_id}/Candidates"
    r2 = zoho_client.session.get(url2, headers=zoho_client._get_headers())
    results["JobOpenings"] = {"status": r2.status_code, "text": r2.text[:200]}

    # 3. Applications Search
    url3 = f"{zoho_client.base_url}/Applications/search"
    r3 = zoho_client.session.get(url3, headers=zoho_client._get_headers(), params={"criteria": f"(Job_Opening_ID:equals:{job_id})"})
    results["Applications_Search_1"] = {"status": r3.status_code, "text": r3.text[:200]}

    # 4. Applications Search 2
    r4 = zoho_client.session.get(url3, headers=zoho_client._get_headers(), params={"criteria": f"(Job_Opening_Id:equals:{job_id})"})
    results["Applications_Search_2"] = {"status": r4.status_code, "text": r4.text[:200]}

    # 5. Candidates Search by Job
    url5 = f"{zoho_client.base_url}/Candidates/search"
    r5 = zoho_client.session.get(url5, headers=zoho_client._get_headers(), params={"criteria": f"(Job_Opening_ID:equals:{job_id})"})
    results["Candidates_Search"] = {"status": r5.status_code, "text": r5.text[:200]}
    
    return results


@router.post("/sync-zoho", status_code=202)
async def sync_zoho_candidates(
    payload: SyncZohoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """
    Fetch candidates from Zoho Recruit and run each through the full LLM
    extraction pipeline. If job_ids are provided in the payload, only fetch
    candidates linked to those specific job openings.


    For each candidate:
      1. Try to download their attached CV/resume from Zoho.
      2. If a CV is found, extract its text and pass to the LLM extractor.
      3. If no CV, build a rich structured text from Zoho fields and pass to LLM.
      4. Queue _process_import as a background task — same as /candidates/upload.

    This ensures ALL fields (employment_history, education, certifications,
    responsibilities, seniority_level, experience_areas, industries, etc.)
    are extracted and stored identically to local KB candidates.
    """
    try:
        zoho_client = ZohoRecruitClient()
        zoho_candidates = []
        if payload.job_ids:
            logger.info(f"[API:ZOHO] Syncing candidates for jobs: {payload.job_ids}")
            # Keep track of seen IDs to avoid syncing the same candidate multiple times
            seen_cand_ids = set()
            for job_id in payload.job_ids:
                apps = zoho_client.get_applications_for_job(job_id)
                for app in apps:
                    # Depending on API response, Candidate ID can be in different fields
                    cand_id = app.get("Candidate_ID") or app.get("$Candidate_Id") or app.get("Candidate", {}).get("id")
                    if cand_id and str(cand_id) not in seen_cand_ids:
                        seen_cand_ids.add(str(cand_id))
                        cand_details = zoho_client.get_candidate_details(str(cand_id))
                        if cand_details:
                            zoho_candidates.append(cand_details)
        else:
            logger.info("[API:ZOHO] No job_ids provided, syncing all candidates.")
            zoho_candidates = zoho_client.get_all_candidates()
    except Exception as e:
        logger.error(f"[API:ZOHO] Failed to fetch candidates from Zoho: {e}")
        raise HTTPException(status_code=503, detail="Failed to connect to Zoho Recruit")

    if not zoho_candidates:
        return {"message": "No candidates found in Zoho Recruit.", "queued_count": 0}

    queued_count = 0
    skipped_count = 0

    for z_cand in zoho_candidates:
        candidate_id = str(z_cand.get("id", ""))
        email_raw = z_cand.get("Email")
        email = normalize_email(email_raw)

        first_name = (z_cand.get("First_Name") or "").strip()
        last_name = (z_cand.get("Last_Name") or "").strip()
        name = f"{first_name} {last_name}".strip() or None

        if not email:
            if candidate_id:
                email = f"{candidate_id}@zoho.local"
            else:
                logger.warning(f"[API:ZOHO] Skipping candidate with no email and no id: {name}")
                skipped_count += 1
                continue

        # ── Build structured fallback text from Zoho fields ──────────────────
        city = (z_cand.get("City") or "").strip()
        country = (z_cand.get("Country") or "").strip()
        location_parts = [p for p in [city, country] if p]
        location = ", ".join(location_parts) or None

        skill_set_raw = z_cand.get("Skill_Set") or ""
        current_title = (z_cand.get("Current_Job_Title") or "").strip() or None
        current_company = (z_cand.get("Current_Employer") or "").strip() or None
        mobile = (z_cand.get("Phone") or z_cand.get("Mobile") or "").strip() or None

        years_experience_raw = z_cand.get("Experience_in_Years", "")
        highest_edu = (z_cand.get("Highest_Qualification_Held") or "").strip()
        department = (z_cand.get("Department") or "").strip()
        linkedin = (z_cand.get("LinkedIn_Profile") or "").strip()

        # Rich structured text that the LLM can extract fields from
        zoho_text = (
            f"Name: {name or ''}\n"
            f"Email: {email}\n"
            f"Current Job Title: {current_title or ''}\n"
            f"Current Employer: {current_company or ''}\n"
            f"Years of Experience: {years_experience_raw}\n"
            f"Skills: {skill_set_raw}\n"
            f"Location: {location or ''}\n"
            f"Phone: {mobile or ''}\n"
            f"Highest Qualification: {highest_edu}\n"
            f"Department: {department}\n"
            f"LinkedIn: {linkedin}\n"
        )

        # ── Attempt to download CV attachment from Zoho ──────────────────────
        raw_text: str | None = None
        if candidate_id:
            try:
                attachments = zoho_client.get_candidate_attachments(candidate_id)
                if attachments:
                    # Pick first attachment (usually the resume)
                    att = attachments[0]
                    att_id = str(att.get("id", ""))
                    if att_id:
                        file_bytes = zoho_client.download_attachment(candidate_id, att_id)
                        if file_bytes:
                            try:
                                from hr_agent.api.deps import extract_pdf_text
                                raw_text = extract_pdf_text(file_bytes)
                                logger.info(
                                    f"[API:ZOHO] Downloaded CV for {email} — "
                                    f"{len(raw_text)} chars extracted from PDF"
                                )
                                # Prepend Zoho structured fields so the LLM has email/name even if CV lacks them
                                raw_text = zoho_text + "\n---\nResume Text:\n" + raw_text
                            except Exception as pdf_err:
                                logger.warning(
                                    f"[API:ZOHO] PDF extraction failed for {email}: {pdf_err} — using Zoho fields"
                                )
            except Exception as att_err:
                logger.warning(f"[API:ZOHO] Could not fetch attachments for {email}: {att_err}")

        # Fall back to Zoho structured text if no CV was downloaded
        if not raw_text:
            raw_text = zoho_text
            logger.info(f"[API:ZOHO] No CV for {email} — using Zoho field text for LLM extraction")

        # ── Create import record and queue the full LLM extraction pipeline ──
        import_row = create_import(
            db,
            raw_text=raw_text,
            source_name="zoho",
            name=name,
            email_hint=email,
            location=location,
        )
        db.commit()

        background_tasks.add_task(
            _process_import,
            import_row.id,
            extraction_svc,
            embedding_svc,
        )
        queued_count += 1
        logger.info(
            f"[API:ZOHO] Queued full extraction for {email} (name={name!r}, "
            f"has_cv={raw_text != zoho_text})"
        )

    logger.info(f"[API:ZOHO] Sync queued {queued_count} candidates, skipped {skipped_count}.")
    return {
        "message": (
            f"Queued {queued_count} Zoho candidates for full LLM extraction "
            f"(same as local CV upload). Skipped {skipped_count}."
        ),
        "queued_count": queued_count,
        "skipped_count": skipped_count,
    }


def _embed_zoho_candidate(
    email: str,
    text: str,
    embedding_svc: EmbeddingService,
) -> None:
    """Background task: generate and store embedding for a Zoho-synced candidate."""
    from hr_agent.database import SessionLocal

    logger.info(f"[BG:ZOHO] Generating embedding for candidate email={email}")
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter_by(email=email).first()
        if candidate is None:
            logger.warning(f"[BG:ZOHO] Candidate {email} not found for embedding.")
            return

        embedding_svc.generate_and_store(db, "candidate", email, text)
        embedding_svc.ensure_fingerprint_embedding(
            db, "candidate", email, build_candidate_fingerprint(candidate)
        )

        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=email, entity_type="candidate")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        if log:
            log.status = ProcessingStatus.EMBEDDED
        db.commit()
        logger.info(f"[BG:ZOHO] Embedding complete for email={email} ✓")
    except Exception as e:
        logger.error(f"[BG:ZOHO] Embedding failed for {email}: {e}")
        db.rollback()
    finally:
        db.close()


def _process_zoho_import(
    import_id: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """
    Background task: Process Zoho form import.
    """
    from hr_agent.database import SessionLocal
    
    logger.info(f"[BG:ZOHO] Processing import — import_id={import_id}")
    
    db = SessionLocal()
    try:
        import_row = db.query(CandidateImport).filter_by(id=import_id).first()
        if import_row is None:
            logger.error(f"[BG:ZOHO] Import {import_id} not found")
            return
        
        if not import_row.raw_text:
            logger.error(f"[BG:ZOHO] No resume text in import {import_id}")
            mark_import_failed(import_row, "Resume text is missing")
            db.commit()
            return
        
        # Step 1: LLM extraction from resume
        logger.info(f"[BG:ZOHO] Step 1/3 — LLM extraction")
        try:
            extracted = extraction_svc.extract_cv(import_row.raw_text)
        except ExtractionError as e:
            logger.error(f"[BG:ZOHO] Extraction failed: {e}")
            mark_import_failed(import_row, str(e))
            db.commit()
            return
        
        # Step 2: Merge Zoho data + extracted data
        logger.info(f"[BG:ZOHO] Step 2/3 — Merging data sources")
        try:
            zoho_data = ZohoFormData(**import_row.zoho_data)
            merge_svc = CandidateMergeService()
            merged = merge_svc.merge_sources(
                zoho_data,
                extracted,
                MergeStrategy(import_row.merge_strategy),
            )
        except Exception as e:
            logger.error(f"[BG:ZOHO] Merge failed: {e}")
            mark_import_failed(import_row, f"Merge error: {e}")
            db.commit()
            return
        
        # Normalize email (use from resume, which is primary key)
        email = normalize_email(merged.email)
        if email is None:
            logger.error(f"[BG:ZOHO] No valid email after merge")
            mark_import_failed(import_row, "No valid email after merge")
            db.commit()
            return
        
        import_row.proposed_email = email
        import_row.extracted_data = merged.to_dict()
        
        # Step 3: Check for duplicates
        existing = db.query(Candidate).filter_by(email=email).first()
        if existing is not None:
            import_row.status = ImportStatus.CONFLICT
            import_row.existing_email = email
            db.commit()
            logger.info(f"[BG:ZOHO] Conflict detected — awaiting resolution")
            return
        
        # Step 4: Create candidate with merged data
        logger.info(f"[BG:ZOHO] Creating candidate with merged data")
        candidate = create_candidate_from_zoho_merge(
            db,
            email=email,
            merged_data=merged,
            raw_text=import_row.raw_text,
            zoho_submission_id=import_row.zoho_submission_id,
            zoho_form_id=import_row.zoho_form_id,
        )
        db.flush()
        
        # Step 5: Domain classification
        logger.info(f"[BG:ZOHO] Step 3/3 — Domain classification")
        try:
            domain_svc = get_domain_classification_service()
            classification = domain_svc.classify_candidate(
                current_title=merged.current_title,
                normalized_role=merged.normalized_role,
                seniority_level=merged.seniority_level,
                industries=merged.industries,
                skills=merged.skills,
                tools=merged.tools_and_technologies,
                responsibilities=merged.responsibilities,
                experience_areas=merged.experience_areas,
                education=merged.education,
                summary=merged.summary,
            )
            apply_domain_to_candidate(candidate, classification)
        except Exception as e:
            logger.warning(f"[BG:ZOHO] Domain classification failed: {e}")
        
        # Step 6: Generate embeddings
        log = (
            db.query(ProcessingLog)
            .filter_by(entity_id=email, entity_type="candidate")
            .order_by(ProcessingLog.updated_at.desc())
            .first()
        )
        
        try:
            embedding_svc.generate_and_store(db, "candidate", email, merged.summary)
            embedding_svc.ensure_fingerprint_embedding(
                db, "candidate", email, build_candidate_fingerprint(candidate)
            )
            if log:
                log.status = ProcessingStatus.EMBEDDED
            delete_import_row(db, import_row)
            db.commit()
            logger.info(f"[BG:ZOHO] Processing complete ✓")
        except Exception as e:
            logger.error(f"[BG:ZOHO] Embedding failed: {e}")
            if log:
                log.status = ProcessingStatus.FAILED
                log.error_message = str(e)
            delete_import_row(db, import_row)
            db.commit()
    
    finally:
        db.close()


@router.post("/import-from-zoho-form", response_model=CandidateUploadResponse, status_code=202)
async def import_candidate_from_zoho_form(
    payload: ZohoFormImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """
    Import candidate from Zoho form submission.
    """
    logger.info(
        f"[API:ZOHO] Import request — submission_id={payload.submission_id} "
        f"merge_strategy={payload.merge_strategy}"
    )
    
    # Step 1: Validate submission exists in Zoho
    try:
        zoho_client = ZohoFormsClient()
        submission = zoho_client.get_form_submission(
            payload.form_id, payload.submission_id
        )
    except ValueError as e:
        logger.error(f"[API:ZOHO] Invalid submission: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[API:ZOHO] Failed to fetch submission: {e}")
        raise HTTPException(status_code=503, detail="Failed to connect to Zoho")
    
    # Step 2: Validate resume attached
    if not zoho_client.validate_submission_has_resume(submission):
        logger.warning(f"[API:ZOHO] No resume in submission {payload.submission_id}")
        raise HTTPException(status_code=422, detail="No resume file attached to this form submission")
    
    # Step 3: Validate required fields
    required_fields = ["email", "name"]  # Configurable
    is_valid, missing = zoho_client.validate_submission_has_required_fields(
        submission, required_fields
    )
    if not is_valid:
        logger.warning(f"[API:ZOHO] Missing fields: {missing}")
        raise HTTPException(
            status_code=400,
            detail=f"Form submission missing required fields: {', '.join(missing)}"
        )
    
    # Step 4: Download resume
    try:
        resume_att = submission.get_resume_attachment()
        resume_bytes = zoho_client.download_file(
            payload.form_id,
            payload.submission_id,
            resume_att["id"]
        )
    except Exception as e:
        logger.error(f"[API:ZOHO] Failed to download resume: {e}")
        raise HTTPException(status_code=422, detail="Failed to download resume from Zoho")
    
    # Step 5: Extract resume text
    try:
        from hr_agent.api.deps import extract_pdf_text
        from hr_agent.core.errors import PDFExtractionError
        raw_text = extract_pdf_text(resume_bytes)
    except Exception as e:
        logger.error(f"[API:ZOHO] PDF extraction failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    
    # Step 6: Extract Zoho form data
    zoho_data = ZohoFormData(
        name=submission.get_field_value("name"),
        email=submission.get_field_value("email"),
        current_title=submission.get_field_value("current_title"),
        current_company=submission.get_field_value("current_company"),
        location=submission.get_field_value("location"),
        years_experience=submission.get_field_value("years_experience"),
    )
    
    # Step 7: Create import record
    import_row = create_import(
        db,
        raw_text=raw_text,
        source_name="zoho_forms",
        name=zoho_data.name,
    )
    import_row.zoho_submission_id = payload.submission_id
    import_row.zoho_form_id = payload.form_id
    import_row.zoho_data = zoho_data.to_dict()
    import_row.merge_strategy = payload.merge_strategy
    
    db.commit()
    
    # Step 8: Queue background processing
    background_tasks.add_task(
        _process_zoho_import,
        import_row.id,
        extraction_svc,
        embedding_svc,
    )
    
    logger.info(
        f"[API:ZOHO] Import queued ✓ — import_id={import_row.id} "
        f"candidate_email={zoho_data.email}"
    )
    
    return CandidateUploadResponse(
        import_id=import_row.id,
        status=ImportStatus.PROCESSING,
        message="Zoho form import queued for processing",
        candidate_email=zoho_data.email,
        zoho_submission_id=payload.submission_id,
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
    from hr_agent.models.job_candidate_pool import JobCandidatePool

    db.query(JobCandidatePool).filter_by(candidate_id=email).delete()
    db.query(Embedding).filter_by(entity_type="candidate", entity_id=email).delete()
    db.query(ProcessingLog).filter_by(entity_type="candidate", entity_id=email).delete()
    db.delete(candidate)
    db.commit()

    logger.info("[API:CV] Candidate deleted — email=%s", email)
    return Response(status_code=204)


@router.delete("", status_code=200)
def delete_candidates_bulk(
    source_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Bulk-delete candidates by source_name (e.g. 'zoho', 'local_kb').
    Also clears all related match results, embeddings, and processing logs.
    If source_name is omitted, deletes ALL candidates (use with caution).
    """
    from hr_agent.models.job_candidate_pool import JobCandidatePool

    query = db.query(Candidate)
    if source_name:
        query = query.filter(Candidate.source_name == source_name)

    candidates = query.all()
    emails = [c.email for c in candidates]

    if not emails:
        return {"deleted_count": 0, "message": "No candidates found."}

    db.query(MatchResult).filter(MatchResult.candidate_id.in_(emails)).delete(synchronize_session=False)
    db.query(JobCandidatePool).filter(JobCandidatePool.candidate_id.in_(emails)).delete(synchronize_session=False)
    db.query(Embedding).filter(
        Embedding.entity_type == "candidate",
        Embedding.entity_id.in_(emails),
    ).delete(synchronize_session=False)
    db.query(ProcessingLog).filter(
        ProcessingLog.entity_type == "candidate",
        ProcessingLog.entity_id.in_(emails),
    ).delete(synchronize_session=False)
    db.query(Candidate).filter(Candidate.email.in_(emails)).delete(synchronize_session=False)

    # Also wipe any pending import records for this source so the queue is clean
    if source_name:
        db.query(CandidateImport).filter(
            CandidateImport.source_name == source_name,
        ).delete(synchronize_session=False)
    else:
        db.query(CandidateImport).delete(synchronize_session=False)

    db.commit()
    label = source_name or "all sources"
    logger.info("[API:CV] Bulk delete — source=%s  deleted=%d candidates", label, len(emails))
    return {
        "deleted_count": len(emails),
        "message": f"Deleted {len(emails)} candidates from {label}.",
    }


@router.delete("/imports/clear", status_code=200)
def clear_pending_imports(
    source_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Clear stuck pending/processing import records without deleting the candidates."""
    query = db.query(CandidateImport)
    if source_name:
        query = query.filter(CandidateImport.source_name == source_name)

    deleted = query.filter(
        CandidateImport.status.in_([ImportStatus.PENDING, ImportStatus.PROCESSING])
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("[API:CV] Cleared %d stuck pending imports (source=%s)", deleted, source_name)
    return {
        "cleared_count": deleted,
        "message": f"Cleared {deleted} stuck pending import records.",
    }


@router.post("/{candidate_email}/classify-domain", response_model=CandidateResponse)
def classify_candidate_domain(
    candidate_email: str,
    db: Session = Depends(get_db),
    domain_svc: DomainClassificationService = Depends(get_domain_classification_service),
):
    """Re-run LLM domain/subdomain classification from current candidate fields."""
    email = normalize_email(candidate_email) or candidate_email
    candidate = db.query(Candidate).filter_by(email=email).first()
    if candidate is None:
        raise NotFoundError(message=f"Candidate {candidate_email!r} not found.")
    if not candidate.normalized_role:
        raise HTTPException(status_code=422, detail="Candidate must be structured before domain classification.")

    try:
        classification = domain_svc.classify_candidate(
            current_title=candidate.current_title,
            normalized_role=candidate.normalized_role,
            seniority_level=candidate.seniority_level,
            industries=candidate.industries,
            skills=candidate.skills,
            tools=candidate.tools_and_technologies,
            responsibilities=candidate.responsibilities,
            experience_areas=candidate.experience_areas,
            education=candidate.education,
            summary=candidate.summary,
        )
        apply_domain_to_candidate(candidate, classification)
        db.commit()
        db.refresh(candidate)
    except DomainClassificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=email, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING
    return _candidate_response(candidate, status)


@router.put("/{candidate_email}/domain", response_model=CandidateResponse)
def update_candidate_domain(
    candidate_email: str,
    body: DomainUpdate,
    db: Session = Depends(get_db),
):
    """Manually set domain and subdomains from the taxonomy."""
    email = normalize_email(candidate_email) or candidate_email
    candidate = db.query(Candidate).filter_by(email=email).first()
    if candidate is None:
        raise NotFoundError(message=f"Candidate {candidate_email!r} not found.")
    try:
        apply_manual_domain(candidate, body.domain_code, body.subdomain_codes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(candidate)

    log = (
        db.query(ProcessingLog)
        .filter_by(entity_id=email, entity_type="candidate")
        .order_by(ProcessingLog.updated_at.desc())
        .first()
    )
    status = log.status if log else ProcessingStatus.PENDING
    return _candidate_response(candidate, status)
