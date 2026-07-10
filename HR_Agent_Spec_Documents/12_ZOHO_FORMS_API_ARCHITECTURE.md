# Zoho Forms Integration - API & Architecture Reference

**Document**: Complete API specifications, sequence diagrams, and technical reference  
**Status**: Ready for development  

---

## Table of Contents

1. [API Specifications](#api-specifications)
2. [Sequence Diagrams](#sequence-diagrams)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Testing Checklist](#testing-checklist)
5. [Troubleshooting Guide](#troubleshooting-guide)

---

## API Specifications

### 1. New Endpoint: POST /candidates/import-from-zoho-form

#### Overview
Import a candidate from a Zoho Form submission. The endpoint fetches the submission, downloads the resume, extracts data, merges with Zoho form data, and processes the candidate asynchronously.

#### Request

```http
POST /candidates/import-from-zoho-form HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "submission_id": "zoho_sub_1234567890",
  "form_id": "zoho_form_9876543210",
  "merge_strategy": "standard"
}
```

**Request Body Schema**:
```python
class ZohoFormImportRequest(BaseModel):
    submission_id: str  # Required: Zoho submission ID
    form_id: str  # Required: Zoho form ID
    merge_strategy: Literal[
        "standard",        # Default: Zoho for structured, resume for rich
        "resume_priority", # Resume takes precedence
        "zoho_priority"    # Zoho takes precedence
    ] = "standard"
```

#### Response (202 Accepted)

```json
{
  "import_id": "import_abc123def456",
  "status": "PROCESSING",
  "message": "Zoho form import queued for processing",
  "candidate_email": "john@example.com",
  "conflict": false,
  "zoho_submission_id": "zoho_sub_1234567890"
}
```

**Response Schema**:
```python
class ZohoFormImportResponse(BaseModel):
    import_id: str
    status: str  # "PROCESSING" | "CONFLICT" | "COMPLETED" | "FAILED"
    message: str
    conflict: bool
    candidate_email: str | None = None
    zoho_submission_id: str | None = None
    error_message: str | None = None
```

#### Error Responses

**404 Not Found** - Submission doesn't exist:
```json
{
  "detail": "Zoho submission zoho_sub_1234567890 not found"
}
```

**422 Unprocessable Entity** - No resume attached:
```json
{
  "detail": "No resume file attached to this form submission"
}
```

**400 Bad Request** - Missing required form fields:
```json
{
  "detail": "Form submission missing required fields: email, name"
}
```

**401 Unauthorized** - Invalid/expired token:
```json
{
  "detail": "Not authenticated"
}
```

#### Background Processing Flow

```
┌─────────────────────────────────────────────────────┐
│ POST /candidates/import-from-zoho-form              │
│ → Create CandidateImport record (PROCESSING)        │
│ → Queue background task                             │
│ → Return 202 ACCEPTED                               │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ Background Task Starts      │
         │ (_process_zoho_import)      │
         └────────────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
      ▼               ▼               ▼
   ┌────┐        ┌────┐         ┌────┐
   │FETCH     │DOWNLOAD   │EXTRACT
   │ZOHO DATA │RESUME     │RESUME
   └────┘     └────┘      └────┘
      │               │               │
      └───────────────┼───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ LLM Extract Resume         │
         │ (extract_cv)               │
         └────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ Merge Data                 │
         │ (merge_sources)            │
         └────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ Check for Duplicates       │
         │ (email lookup)             │
         └────────────────────────────┘
                      │
      ┌───────────────┴───────────────┐
      │                               │
      ▼                               ▼
  ┌─────────┐                    ┌──────────┐
  │NEW EMAIL│                    │DUPLICATE │
  │         │                    │EMAIL     │
  └────┬────┘                    └────┬─────┘
       │                              │
       ▼                              ▼
  ┌────────────┐             ┌────────────────┐
  │CREATE      │             │MARK CONFLICT   │
  │CANDIDATE   │             │(awaiting user) │
  └────┬───────┘             └────────────────┘
       │
       ▼
  ┌────────────────────┐
  │DOMAIN             │
  │CLASSIFICATION     │
  └────┬───────────────┘
       │
       ▼
  ┌────────────────────┐
  │GENERATE           │
  │EMBEDDINGS         │
  └────┬───────────────┘
       │
       ▼
  ┌────────────────────┐
  │MARK COMPLETE       │
  │DELETE IMPORT RECORD│
  └────────────────────┘
```

#### Implementation Code

```python
# In hr_agent/api/candidates.py

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
    
    Process:
    1. Fetch form submission from Zoho
    2. Validate required fields present
    3. Download resume file
    4. Extract resume text
    5. Queue background processing (merge + LLM extraction)
    
    Returns 202 ACCEPTED with import_id for polling status.
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
        raw_text = extract_pdf_text(resume_bytes)
    except PDFExtractionError as e:
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
        # ... other fields based on form schema
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


def _process_zoho_import(
    import_id: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """
    Background task: Process Zoho form import.
    
    Steps:
    1. Extract candidate data from resume
    2. Merge with Zoho form data
    3. Check for duplicate email
    4. Create/update candidate
    5. Domain classification
    6. Generate embeddings
    """
    from hr_agent.database import SessionLocal
    from hr_agent.services.candidate_merge_service import CandidateMergeService
    
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
```

---

### 2. Updated Existing Endpoints

#### GET /candidates/{email}

**Response Extended** (add optional Zoho fields):

```json
{
  "email": "john@example.com",
  "name": "John Doe",
  "current_title": "Senior Engineer",
  "normalized_role": "engineer",
  "years_experience": 10,
  "current_company": "Acme Corp",
  "location": "New York, USA",
  "skills": ["Python", "Go", "JavaScript"],
  "tools_and_technologies": ["Docker", "Kubernetes"],
  "education": [
    {
      "degree": "Bachelor of Science",
      "institution": "MIT",
      "year": 2014
    }
  ],
  "certifications": ["AWS Solutions Architect"],
  "employment_history": [
    {
      "title": "Senior Engineer",
      "company": "Acme Corp",
      "start_date": "2020-01-01",
      "end_date": "Present"
    }
  ],
  "industries": ["Technology"],
  "experience_areas": ["Backend", "DevOps"],
  "responsibilities": ["Architecture", "Team Leadership"],
  "seniority_level": "Senior",
  "summary": "Experienced full-stack engineer...",
  
  "domain_code": "tech_backend",
  "domain_label": "Backend Engineering",
  "subdomain_codes": ["devops", "infrastructure"],
  "domain_confidence": 0.92,
  
  // NEW: Zoho-specific fields
  "zoho_submission_id": "zoho_sub_1234567890",
  "zoho_form_id": "zoho_form_9876543210",
  "data_sources": {
    "name": ["zoho"],
    "current_title": ["zoho"],
    "skills": ["zoho", "resume"],
    "employment_history": ["resume"],
    "summary": ["resume"]
  },
  
  "source_name": "zoho_forms",  // "local_kb" or "zoho_forms"
  "status": "EMBEDDED",
  "created_at": "2026-07-09T12:34:56Z"
}
```

---

## Sequence Diagrams

### Scenario 1: Successful Zoho Import (New Candidate)

```
┌─────────┐           ┌──────────┐      ┌─────────┐      ┌────────┐
│  Client │           │ API      │      │ Zoho    │      │Database│
└────┬────┘           └────┬─────┘      └────┬────┘      └───┬────┘
     │                     │                  │               │
     │ POST /import-zoho   │                  │               │
     ├────────────────────>│                  │               │
     │                     │                  │               │
     │                     │ fetch_submission │               │
     │                     ├─────────────────>│               │
     │                     │  ◄───────────────┤               │
     │                     │  FormSubmission  │               │
     │                     │                  │               │
     │                     │ download_resume  │               │
     │                     ├─────────────────>│               │
     │                     │  ◄───────────────┤               │
     │                     │  resume.pdf      │               │
     │                     │                  │               │
     │                     │ extract_pdf_text │               │
     │                     │  (internal)      │               │
     │                     │                  │               │
     │                     │  create_import   │               │
     │                     ├────────────────────────────────->│
     │                     │   CandidateImport PROCESSING     │
     │                     │  ◄────────────────────────────────│
     │                     │  import_id                        │
     │                     │                  │               │
     │ 202 ACCEPTED        │                  │               │
     │ {import_id, ...}    │                  │               │
     │<────────────────────┤                  │               │
     │                     │                  │               │
     │ [Background Task]   │                  │               │
     │                     │ extract_cv       │               │
     │                     │  (LLM)           │               │
     │                     │                  │               │
     │                     │ merge_sources    │               │
     │                     │  (merge logic)   │               │
     │                     │                  │               │
     │                     │ check duplicate  │               │
     │                     ├────────────────────────────────->│
     │                     │  query by email  │               │
     │                     │  ◄────────────────────────────────│
     │                     │  (no duplicate)  │               │
     │                     │                  │               │
     │                     │ create_candidate │               │
     │                     ├────────────────────────────────->│
     │                     │  INSERT Candidate               │
     │                     │  ◄────────────────────────────────│
     │                     │  ✓                               │
     │                     │                  │               │
     │                     │ domain_classify  │               │
     │                     │ gen_embeddings   │               │
     │                     │                  │               │
     │                     │ update_import    │               │
     │                     ├────────────────────────────────->│
     │                     │  DELETE CandidateImport         │
     │                     │  ◄────────────────────────────────│
     │                     │  ✓                               │
     │                     │                  │               │
     │ GET /imports/{id}   │                  │               │
     ├────────────────────>│                  │               │
     │                     │ query_import     │               │
     │                     ├────────────────────────────────->│
     │                     │  (not found - deleted)           │
     │                     │  ◄────────────────────────────────│
     │                     │                  │               │
     │ GET /candidates/    │                  │               │
     │     email           │                  │               │
     ├────────────────────>│                  │               │
     │                     │ query_candidate  │               │
     │                     ├────────────────────────────────->│
     │                     │  SELECT Candidate               │
     │                     │  ◄────────────────────────────────│
     │                     │  {merged data...}               │
     │ CandidateResponse   │                  │               │
     │ ✓ COMPLETED         │                  │               │
     │<────────────────────┤                  │               │
```

### Scenario 2: Zoho Import with Email Conflict

```
┌─────────┐           ┌──────────┐      ┌─────────┐      ┌────────┐
│  Client │           │ API      │      │ Zoho    │      │Database│
└────┬────┘           └────┬─────┘      └────┬────┘      └───┬────┘
     │                     │                  │               │
     │ POST /import-zoho   │                  │               │
     ├────────────────────>│                  │               │
     │                     │ [fetch & prep]   │               │
     │                     │                  │               │
     │ 202 ACCEPTED        │                  │               │
     │<────────────────────┤                  │               │
     │                     │                  │               │
     │ [Background Task]   │                  │               │
     │                     │ [extract & merge]│               │
     │                     │                  │               │
     │                     │ check duplicate  │               │
     │                     ├────────────────────────────────->│
     │                     │  query by email  │               │
     │                     │  ◄────────────────────────────────│
     │                     │  EXISTS!         │               │
     │                     │                  │               │
     │                     │ mark_conflict    │               │
     │                     ├────────────────────────────────->│
     │                     │  UPDATE CandidateImport        │
     │                     │  status = CONFLICT             │
     │                     │  ◄────────────────────────────────│
     │                     │  ✓                               │
     │                     │                  │               │
     │ GET /imports/       │                  │               │
     │ conflicts           │                  │               │
     ├────────────────────>│                  │               │
     │                     │ query_conflicts  │               │
     │                     ├────────────────────────────────->│
     │                     │  SELECT where status=CONFLICT   │
     │                     │  ◄────────────────────────────────│
     │                     │  [import data]   │               │
     │ ConflictResponse    │                  │               │
     │ (proposed + exist)  │                  │               │
     │<────────────────────┤                  │               │
     │                     │                  │               │
     │ [User chooses]      │                  │               │
     │ POST /imports/{id}  │                  │               │
     │ /resolve            │                  │               │
     │ {action: "update"}  │                  │               │
     ├────────────────────>│                  │               │
     │                     │ apply_merge      │               │
     │                     ├────────────────────────────────->│
     │                     │  UPDATE Candidate               │
     │                     │  with merged data               │
     │                     │  ◄────────────────────────────────│
     │                     │                  │               │
     │                     │ domain_classify  │               │
     │                     │ gen_embeddings   │               │
     │ 200 OK              │                  │               │
     │ {updated candidate} │                  │               │
     │<────────────────────┤                  │               │
```

---

## Data Flow Diagrams

### Field Merge Flow (STANDARD Strategy)

```
Input: Zoho Form Data + Resume Extraction
       ├─ name (Zoho): "John Doe"
       ├─ name (Resume): "John D."
       ├─ email (Zoho): "john@company.com"
       ├─ email (Resume): "john@gmail.com"
       ├─ skills (Zoho): ["Python", "JavaScript"]
       └─ skills (Resume): ["Python", "Go"]

Process (STANDARD strategy):
       
name:
       Zoho: "John Doe" ──┐
                          ├─> "John Doe" (ZOHO priority)
       Resume: "John D." ─┘

email:
       Zoho: "john@company.com" ──┐
                                  ├─> "john@gmail.com" (RESUME - primary key)
       Resume: "john@gmail.com" ──┘

skills:
       Zoho: ["Python", "JavaScript"]     ┐
                                          ├─> ["go", "javascript", "python"]
       Resume: ["Python", "Go"]           ├   (UNION - deduplicated)
                                          └   (sources: ["zoho", "resume"])

Output:
       {
         "name": "John Doe",
         "email": "john@gmail.com",
         "skills": ["go", "javascript", "python"],
         "data_sources": {
           "name": ["zoho"],
           "email": ["resume"],
           "skills": ["zoho", "resume"]
         }
       }
```

---

## Testing Checklist

### Unit Tests

**Files to create/update**:
- [x] `tests/test_zoho_forms_client.py`
- [x] `tests/test_candidate_merge_service.py`
- [ ] `tests/test_zoho_import_endpoint.py` (new)
- [ ] `tests/test_zoho_import_background_task.py` (new)

**Test Coverage**:

```
ZohoFormsClient:
  ✓ fetch_form_submission() success
  ✓ fetch_form_submission() not found
  ✓ fetch_form_submission() network error
  ✓ download_file() success
  ✓ download_file() timeout
  ✓ download_file() invalid file_id
  ✓ validate_submission_has_required_fields() all present
  ✓ validate_submission_has_required_fields() missing fields
  ✓ validate_submission_has_resume() has pdf
  ✓ validate_submission_has_resume() no pdf
  ✓ rate limiting retry logic
  ✓ oauth token refresh

CandidateMergeService:
  ✓ merge_standard_strategy_name_zoho_priority
  ✓ merge_standard_strategy_email_resume_priority
  ✓ merge_standard_strategy_skills_union
  ✓ merge_resume_priority_strategy
  ✓ merge_zoho_priority_strategy
  ✓ merge_empty_zoho_field_uses_resume
  ✓ merge_empty_resume_field_uses_zoho
  ✓ merge_both_empty_field_null
  ✓ merge_list_deduplication
  ✓ merge_numeric_field_years_experience
  ✓ merge_tracks_data_sources_correctly
  ✓ merge_validates_email_conflicts
  ✓ merge_handles_invalid_data

API Endpoint:
  ✓ POST /import-zoho-form valid request returns 202
  ✓ POST /import-zoho-form invalid form_id returns 404
  ✓ POST /import-zoho-form no resume returns 422
  ✓ POST /import-zoho-form missing fields returns 400
  ✓ POST /import-zoho-form unknown merge_strategy returns 422
  ✓ POST /import-zoho-form unauthenticated returns 401
  ✓ POST /import-zoho-form creates import record
  ✓ POST /import-zoho-form queues background task
```

### Integration Tests

```
✓ End-to-end import: Zoho form → resume → extract → merge → candidate
✓ Import creates candidate with correct merged data
✓ Import triggers domain classification
✓ Import generates embeddings
✓ Import with conflict: shows conflict UI
✓ Import with conflict resolution: update action works
✓ Import with conflict resolution: keep action works
✓ Import handles missing Zoho fields gracefully
✓ Import handles network errors gracefully
✓ Existing resume upload (POST /upload) still works
✓ Existing candidate detail endpoint works with new fields
✓ Existing conflict resolution works for Zoho imports
```

### Load Tests

```
✓ Can handle 100 concurrent Zoho imports
✓ Rate limiting prevents API throttling
✓ Database indices on zoho_submission_id perform well
✓ Merge logic completes in < 1 second
✓ Background task processes 100 imports without memory leak
```

### Regression Tests

```
✓ All existing POST /candidates/upload tests pass
✓ All existing GET /candidates/{email} tests pass
✓ All existing GET /candidates/imports tests pass
✓ All existing conflict resolution tests pass
✓ All existing domain classification tests pass
✓ All existing embedding tests pass
```

### Manual Testing Checklist

```
Pre-Launch:
  [ ] Deploy to staging
  [ ] Test Zoho OAuth with real Zoho account
  [ ] Test form submission with real form
  [ ] Test resume download from Zoho
  [ ] Verify database migration applies cleanly
  [ ] Monitor background task processing
  [ ] Check logging output for errors
  [ ] Verify email notifications still work
  [ ] Test rollback procedure
  
Post-Launch (48 hours):
  [ ] Monitor error rates
  [ ] Monitor performance metrics
  [ ] Check data quality (merged candidates)
  [ ] Verify embeddings generated correctly
  [ ] Test on-call handling of errors
```

---

## Troubleshooting Guide

### Common Issues & Solutions

#### Issue 1: "No resume file attached to this form submission"

**Cause**: Zoho form submission exists but has no PDF attachment

**Solution**:
1. Verify form design includes file upload field
2. Check user uploaded a PDF (not other format)
3. Check file permissions in Zoho (ensure API user can access)
4. Look at `get_resume_attachment()` logic - update if PDF is named differently

**Debug**:
```python
submission = zoho_client.get_form_submission(form_id, submission_id)
print("Attachments:", submission.attachments)
print("Has resume:", submission.get_resume_attachment())
```

#### Issue 2: "Form submission missing required fields: email, name"

**Cause**: Zoho form doesn't have required fields filled or field names are wrong

**Solution**:
1. Verify field names match form schema
2. Require fields in Zoho form design
3. Update required fields list in `POST /import-zoho-form` handler
4. Map Zoho field names correctly

**Debug**:
```python
submission = zoho_client.get_form_submission(form_id, submission_id)
print("Form fields:", submission.fields.keys())
print("Field values:", submission.fields)
```

#### Issue 3: Email mismatch between Zoho and resume

**Cause**: User entered different email in form vs resume

**Solution**:
- Primary key uses resume email (merge priority rule)
- Zoho email is captured in metadata but not used as key
- User sees merged data with resume email
- Log discrepancy for audit trail

**Expected Behavior**:
```json
{
  "email": "john@gmail.com",  // From resume
  "data_sources": {
    "email": ["resume"]  // Where it came from
  }
  // Zoho email is NOT stored, but could add as optional field
}
```

#### Issue 4: Duplicate email conflict with existing candidate

**Cause**: Candidate with same email already exists in system

**Solution**:
1. Conflict resolution UI shows proposed vs existing
2. User chooses: "update" (overwrite) or "keep" (discard import)
3. On "update": Merge replaces existing candidate data
4. On "keep": Import is discarded, existing unchanged

**Flow**:
```
POST /import-zoho-form → Background task → Duplicate detected
                           ↓
                      CandidateImport.status = "CONFLICT"
                           ↓
                      GET /imports/conflicts (shows to user)
                           ↓
                      User chooses action
                           ↓
                      POST /imports/{id}/resolve
                           ↓
                      Apply or discard
```

#### Issue 5: LLM extraction fails for resume

**Cause**: Resume PDF is corrupted, unreadable, or in wrong format

**Solution**:
1. Check PDF is valid (can extract text)
2. Check file size < configured limit
3. Check PDF doesn't have image-only pages
4. Try manual OCR if needed (future enhancement)

**Debug**:
```python
from hr_agent.services.pdf_service import extract_text
try:
    text = extract_text(pdf_bytes)
    print(f"Extracted {len(text)} characters")
except Exception as e:
    print(f"PDF extraction failed: {e}")
```

#### Issue 6: Zoho API rate limit exceeded

**Cause**: Too many requests to Zoho API (429 response)

**Solution**:
- Retry logic automatically handles 429 (exponential backoff)
- Check Zoho API rate limits (typically 5000 req/day)
- Batch imports if possible
- Implement request throttling

**Debug**:
```
# Check logs for:
[ZOHO:FORMS] Request failed after retries: ...
# Indicates retry exhausted - switch to manual retry or schedule later
```

#### Issue 7: Merge creates unexpected values

**Cause**: Merge strategy not applied correctly

**Solution**:
1. Check merge_strategy parameter (default: "standard")
2. Verify merge precedence rules match expectations
3. Check data_sources metadata for actual sources used
4. Review merge logic code

**Debug**:
```python
merged = merge_service.merge_sources(
    zoho_data, extracted, MergeStrategy.STANDARD
)
print("Merged data:", merged.to_dict())
print("Data sources:", merged.data_sources)
```

#### Issue 8: Background task hangs or times out

**Cause**: LLM extraction taking > 5 minutes, database lock, or network issue

**Solution**:
1. Check celery/background task logs
2. Verify database connections are not exhausted
3. Check LLM API availability
4. Increase task timeout if needed

**Monitoring**:
```python
# Log processing steps with timestamps
[BG:ZOHO] Step 1/3 — LLM extraction — started_at=2026-07-09T12:34:56Z
[BG:ZOHO] Step 1/3 — LLM extraction — completed_at=2026-07-09T12:35:12Z
# If gap > 5 min, investigate LLM API
```

### Performance Optimization

**If Zoho imports are slow**:

1. **Add database indexes** (already in migration):
   ```sql
   CREATE INDEX ix_candidates_zoho_submission_id ON candidates(zoho_submission_id);
   CREATE INDEX ix_candidate_imports_zoho_submission_id ON candidate_imports(zoho_submission_id);
   ```

2. **Cache Zoho form schema**:
   ```python
   # Cache form field mapping to avoid repeated API calls
   @cache.cached(timeout=3600)
   def get_form_field_mapping(form_id: str) -> dict:
       # Fetch and cache form schema
   ```

3. **Batch background task processing**:
   - Process multiple imports in parallel (if using Celery)
   - Use connection pooling

4. **Optimize merge logic**:
   - Pre-compute field deduplication
   - Cache merge service instance

### Data Validation

**Verify merged data quality**:

```python
# After merge, validate key fields
merged = merge_service.merge_sources(zoho_data, extracted)

assert merged.email is not None, "Email must not be None"
assert isinstance(merged.skills, list), "Skills must be list"
assert all(isinstance(s, str) for s in merged.skills), "Skills must be strings"
assert len(merged.data_sources) > 0, "Must track sources"

logger.info(f"Merged data valid ✓")
```

