# Zoho Forms Integration - Implementation Checklist

## Backend Implementation (Required)

### ✓ Phase 1: Create Core Services

- [ ] **Create `hr_agent/services/zoho/forms_client.py`**
  - Fetch form submissions from Zoho API
  - Download resume attachments
  - Validate form data
  - (See specification document for full code)

- [ ] **Create `hr_agent/services/candidate_merge_service.py`**
  - Merge Zoho form data + resume extraction
  - Track data sources per field
  - Handle merge conflicts
  - (See specification document for full code)

- [ ] **Create Database Migration**
  ```bash
  alembic revision --autogenerate -m "Add Zoho Forms fields"
  ```
  - Add columns to `candidates` table:
    - `zoho_submission_id` (String)
    - `zoho_form_id` (String)
    - `data_source_metadata` (JSON)
    - `last_zoho_sync` (DateTime)
  - Add columns to `candidate_imports` table:
    - `zoho_submission_id` (String)
    - `zoho_form_id` (String)
    - `zoho_data` (JSON)
    - `merge_strategy` (String)
  - Create indexes on `zoho_submission_id`

- [ ] **Apply Migration**
  ```bash
  cd /Users/shabbirgovernor/Downloads/Aayushi/hr-agent
  alembic upgrade head
  ```

### ✓ Phase 2: Extend Models & Schemas

- [ ] **Update `hr_agent/models/candidate.py`**
  - Add 4 new columns (as per migration)

- [ ] **Update `hr_agent/models/candidate_import.py`**
  - Add 4 new columns (as per migration)

- [ ] **Update `hr_agent/schemas/candidate.py`**
  ```python
  class CandidateResponse(BaseModel):
      # ... existing fields ...
      zoho_submission_id: str | None = None
      zoho_form_id: str | None = None
      data_sources: dict[str, list[str]] = Field(default_factory=dict)
  ```

### ✓ Phase 3: Update Services

- [ ] **Update `hr_agent/services/candidate_service.py`**
  - Add `apply_merge_to_candidate()` function
  - Add `create_candidate_from_zoho_merge()` function

- [ ] **Update `hr_agent/api/candidates.py`**
  - Add `POST /candidates/import-from-zoho-form` endpoint
  - Add `_process_zoho_import()` background task
  - Update existing functions to handle merge strategy

### ✓ Phase 4: Frontend Updates (Already Done ✓)

- [ ] **Update `CandidatesPage.tsx`** ✓
  - Added purple badge for zoho_forms source
  - Source filter now includes zoho_forms

- [ ] **Update `useSources.ts`** ✓
  - Candidate interface now includes Zoho fields
  - `zoho_submission_id`, `zoho_form_id`, `data_sources`

---

## Why Zoho Candidates Aren't Visible Right Now

| Component | Status | Issue |
|-----------|--------|-------|
| Zoho Forms Client | ❌ Not Created | Can't fetch form submissions |
| Merge Service | ❌ Not Created | Can't merge data |
| API Endpoint | ❌ Not Created | No way to import from Zoho |
| Database Columns | ❌ Not Migrated | Fields don't exist in DB |
| Frontend | ✅ Ready | Updated to show zoho_forms |

---

## Quick Implementation Path

### Step 1: Database Migration (5 min)
```bash
cd /Users/shabbirgovernor/Downloads/Aayushi/hr-agent

# Create migration
alembic revision --autogenerate -m "Add Zoho Forms integration fields"

# Check migrations/versions/ folder
ls migrations/versions/ | tail -1

# Apply migration
alembic upgrade head
```

### Step 2: Create Core Services (1-2 hours)
- Copy code from `HR_Agent_Spec_Documents/11_ZOHO_FORMS_IMPLEMENTATION_TIMELINE.md`
- Create `forms_client.py` (250+ lines)
- Create `candidate_merge_service.py` (400+ lines)

### Step 3: Extend Models (15 min)
- Add 4 columns to candidate.py
- Add 4 columns to candidate_import.py

### Step 4: Update Schemas (15 min)
- Add Zoho fields to CandidateResponse

### Step 5: Implement API Endpoint (1 hour)
- Add POST /candidates/import-from-zoho-form
- Add _process_zoho_import background task

### Step 6: Test (1-2 hours)
- Unit tests for merge logic
- Integration tests for import flow

---

## Testing Zoho Integration

Once implemented:

```bash
# 1. Import candidate from Zoho form
curl -X POST "http://localhost:8000/candidates/import-from-zoho-form" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": "zoho_sub_123",
    "form_id": "zoho_form_456",
    "merge_strategy": "standard"
  }'

# 2. View candidate with data sources
curl "http://localhost:8000/candidates/john@example.com" \
  -H "Authorization: Bearer <token>"

# 3. Filter by zoho_forms source
curl "http://localhost:8000/candidates?source_name=zoho_forms" \
  -H "Authorization: Bearer <token>"
```

---

## Git Branch

You're on: `zoho_candidate`

```bash
# Commit your work when ready
git add .
git commit -m "Add Zoho Forms integration - Phase 1-3"
```

---

## Documentation

All code samples are in:
- `HR_Agent_Spec_Documents/10_ZOHO_FORMS_INTEGRATION_SPEC.md` - Specification
- `HR_Agent_Spec_Documents/11_ZOHO_FORMS_IMPLEMENTATION_TIMELINE.md` - Implementation with code
- `HR_Agent_Spec_Documents/12_ZOHO_FORMS_API_ARCHITECTURE.md` - API details

---

## Current Status

✅ **Frontend**: Ready for Zoho Forms (purple badge, type definitions)  
❌ **Backend**: Awaiting implementation (services, API, migration)  
❌ **Database**: Awaiting migration (new columns)  

Once backend is implemented, Zoho candidates will automatically appear in the UI! 🚀

