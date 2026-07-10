# Zoho Forms Integration Specification

**Status**: Design Phase  
**Date**: 2026-07-09  
**Objective**: Extend candidate extraction with Zoho Forms as additional data source while preserving existing resume processing pipeline

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Workflow Analysis](#current-workflow-analysis)
3. [New Workflow](#new-workflow)
4. [Architecture Design](#architecture-design)
5. [Data Integration Strategy](#data-integration-strategy)
6. [API Changes](#api-changes)
7. [Data Model Changes](#data-model-changes)
8. [Implementation Plan](#implementation-plan)
9. [Risk Analysis](#risk-analysis)
10. [Testing Strategy](#testing-strategy)

---

## Executive Summary

### Objective
Introduce **Zoho Forms as an additional candidate data source** without disrupting the existing resume-based extraction pipeline.

### Key Principles
- **Non-breaking**: Existing APIs remain functional
- **Additive**: New endpoints added, not replacing old ones
- **Smart merging**: Zoho structured data + LLM-extracted resume data
- **Precedence-driven**: Clear rules for field conflicts

### Expected Outcome
Candidates can be sourced from two paths:
1. **Resume-first** (existing): Upload PDF → Extract → Store
2. **Form-first** (new): Zoho Form submission → Download resume → Extract & merge

---

## Current Workflow Analysis

### Existing Candidate Ingestion Pipeline

```
┌─────────────────┐
│  User uploads   │
│  PDF Resume     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Extract PDF text           │
│  (pdf_service.py)           │
└────────┬────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Create CandidateImport      │
│  (staging record)            │
│  Status: PROCESSING          │
└────────┬─────────────────────┘
         │
         ▼ (Background Task)
┌──────────────────────────────┐
│  LLM Extraction              │
│  (extraction_service)        │
│  Input: raw_text             │
│  Output: CVExtracted schema  │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Check for duplicate email   │
│  (candidate_service)         │
└────────┬─────────────────────┘
         │
    ┌────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌─────────────┐
│New     │  │Duplicate    │
│Email   │  │Email→CONFLICT
└───┬────┘  └─────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Create Candidate record    │
│  apply_extraction_to_       │
│  candidate()                │
└────────┬────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Domain Classification       │
│  (domain_classification_     │
│   service)                   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Generate Embeddings         │
│  (embedding_service)         │
│  Status: EMBEDDED            │
└────────┬─────────────────────┘
         │
         ▼
┌─────────────────┐
│  Delete Import  │
│  Record (mark   │
│  COMPLETED)     │
└────────┬────────┘
         │
         ▼
    ┌─────────┐
    │COMPLETE │
    └─────────┘
```

### Current Data Flow
- **Input**: PDF file bytes
- **Processing**: Single source (resume only)
- **Extraction**: LLM-based (GPT-4o)
- **Storage**: Candidate model
- **Conflict Resolution**: Email-based deduplication

### Relevant Code Files

| File | Role |
|------|------|
| `hr_agent/api/candidates.py` | Upload endpoint, conflict resolution |
| `hr_agent/services/candidate_service.py` | Email normalization, creation logic |
| `hr_agent/services/extraction_service.py` | LLM extraction |
| `hr_agent/services/pdf_service.py` | PDF text extraction |
| `hr_agent/models/candidate.py` | Database schema |
| `hr_agent/models/candidate_import.py` | Staging model |
| `hr_agent/schemas/candidate.py` | Pydantic schemas |
| `hr_agent/services/candidate_sources/` | Multi-source plugin system |

---

## New Workflow

### Extended Candidate Ingestion with Zoho Forms

```
┌─────────────────────────────────────┐
│  Candidate submits Zoho Form with   │
│  • Structured data (name, email...  │
│  • Resume attachment                │
└────────────┬────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  POST /candidates/import-from-zoho   │
│  Request: {                          │
│    submission_id: "zoho_sub_xyz"     │
│    form_id: "zoho_form_123"          │
│  }                                   │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  ZohoFormsClient.fetch_submission()  │
│  Returns:                            │
│  • Zoho structured data              │
│  • Resume file ID                    │
│  • Metadata                          │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Download Resume from Zoho           │
│  ZohoFormsClient.download_resume()   │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Extract PDF text                    │
│  (reuse existing pdf_service)        │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Create CandidateImport              │
│  Status: PROCESSING                  │
│  source_name: "zoho_forms"           │
│  metadata: { zoho_data: {...} }      │
└────────┬──────────────────────────────┘
         │
         ▼ (Background Task)
┌──────────────────────────────────────┐
│  LLM Extraction from Resume          │
│  Input: resume raw_text              │
│  Output: CVExtracted schema          │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Merge Zoho Data + Extracted Data    │
│  candidate_merge_service.merge()     │
│  Strategy: Zoho for structured,      │
│            Resume for rich fields    │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Check for duplicate email           │
│  (existing logic)                    │
└────────┬──────────────────────────────┘
         │
    ┌────┴──────┐
    │            │
    ▼            ▼
┌────────┐   ┌──────────────┐
│New     │   │Duplicate →   │
│Email   │   │CONFLICT      │
└───┬────┘   └──────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│  Create/Update Candidate             │
│  Include:                            │
│  • Merged extracted data             │
│  • Zoho metadata                     │
│  • Data source tracking              │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Domain Classification               │
│  (existing logic)                    │
└────────┬──────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Generate Embeddings                 │
│  (existing logic)                    │
│  Status: EMBEDDED                    │
└────────┬──────────────────────────────┘
         │
         ▼
    ┌─────────┐
    │COMPLETE │
    └─────────┘
```

### Key Differences from Existing Flow
1. **Additional input**: Zoho structured data
2. **Additional step**: Resume download + merge logic
3. **New metadata**: Track data source origin per field
4. **Same downstream**: Domain classification, embeddings, conflict resolution

---

## Architecture Design

### System Components

#### 1. Zoho Forms Client (`zoho_forms_client.py`)

**Purpose**: Fetch form submissions and resumes from Zoho

**Interface**:
```python
class ZohoFormsClient:
    def get_form_submission(self, submission_id: str) -> FormSubmission
    def download_resume_file(self, file_id: str) -> bytes
    def list_forms(self) -> List[ZohoForm]
    def validate_submission(self, submission: FormSubmission) -> bool
```

**Responsibilities**:
- Authenticate with Zoho OAuth
- Fetch form submission data
- Download attached files
- Handle rate limiting & retries
- Parse Zoho form field mappings

#### 2. Candidate Merge Service (`candidate_merge_service.py`)

**Purpose**: Intelligently combine Zoho form data + resume extraction

**Interface**:
```python
class CandidateMergeService:
    def merge_sources(
        self,
        zoho_data: ZohoFormData,
        extracted: CVExtracted,
        merge_strategy: MergeStrategy,
    ) -> MergedCandidateData
```

**Responsibilities**:
- Define field-level merge logic
- Apply precedence rules
- Validate merged data
- Track data source per field
- Handle missing/conflicting values

#### 3. Candidate Import Handler Update

**Extend** existing `candidate_service.py` with:

```python
def apply_merge_to_candidate(
    candidate: Candidate,
    merged_data: MergedCandidateData,
) -> None
    """Apply merged Zoho + extracted data to candidate record."""
```

#### 4. API Endpoint Handler

**New endpoint** in `candidates.py`:

```python
@router.post("/import-from-zoho-form")
async def import_candidate_from_zoho_form(
    payload: ZohoFormImportRequest,
    background_tasks: BackgroundTasks,
) -> CandidateUploadResponse
```

---

## Data Integration Strategy

### Field Mapping: Zoho Form → Candidate Model

| Candidate Field | Zoho Field | Resume Extract | Merge Priority |
|-----------------|-----------|-----------------|-----------------|
| `name` | First Name + Last Name | candidate_name | Zoho (if both exist, use Zoho) |
| `email` | Email | email (extracted) | Resume (as primary key) |
| `current_title` | Current Job Title | current_title | Zoho first, fallback to resume |
| `current_company` | Current Employer | current_company | Zoho first, fallback to resume |
| `location` | City + Country (form) | location (extracted) | Merge (Zoho as primary) |
| `skills` | Skills (form field) | skills (extracted) | **Union** (combine both) |
| `years_experience` | Years of Experience (field) | years_experience | Zoho if numeric & valid |
| `seniority_level` | Seniority Level (if form field) | seniority_level | Zoho first |
| `education` | — | education (extracted) | Resume only |
| `employment_history` | — | employment_history (extracted) | Resume only |
| `certifications` | Certifications (if form field) | certifications (extracted) | Union |
| `tools_and_technologies` | — | tools_and_technologies | Resume only |
| `industries` | Industry (if form field) | industries (extracted) | Union |
| `experience_areas` | — | experience_areas (extracted) | Resume only |
| `responsibilities` | — | responsibilities (extracted) | Resume only |
| `summary` | About/Bio (if form field) | summary (extracted) | Resume (more detailed) |
| `seniority_level` | — | seniority_level (extracted) | Resume (from extraction) |

### Merge Precedence Rules

```
1. PRIMARY KEYS (must use resume extraction):
   - email (from extracted resume or fallback to Zoho)

2. ZOHO PRIORITY (use Zoho if present and valid):
   - current_title
   - current_company
   - seniority_level (if available in form)
   - years_experience (if numeric)

3. UNION STRATEGY (combine both sources):
   - skills: Union (remove duplicates)
   - certifications: Union (remove duplicates)
   - industries: Union (remove duplicates)

4. RESUME ONLY (ignore Zoho, use extracted):
   - employment_history (Zoho typically doesn't have detailed history)
   - education (form usually doesn't capture in structured form)
   - tools_and_technologies (resume specific)
   - experience_areas (extracted from context)
   - responsibilities (from work history text)

5. FALLBACK STRATEGY:
   - If Zoho field is empty → use extracted value
   - If extracted value is empty → use Zoho field
   - If both empty → leave NULL
   - If conflict → log discrepancy and use primary source
```

### Data Source Tracking

Store metadata to track field origins:

```python
@dataclass
class FieldSource:
    field_name: str
    value: Any
    sources: List[str]  # ["zoho", "resume"]
    primary_source: str  # "zoho" or "resume"
    confidence: float  # 0.0-1.0
```

Extended Candidate model includes:

```python
source_metadata: dict = {
    "current_title": {"primary": "zoho", "sources": ["zoho"]},
    "skills": {"primary": "resume", "sources": ["zoho", "resume"], "merged": True},
    "employment_history": {"primary": "resume", "sources": ["resume"]},
    # ...
}
```

---

## API Changes

### 1. Existing APIs (Backward Compatible)

#### POST /candidates/upload
**No changes to request/response**
- Continues to accept PDF upload
- source_name defaults to "local_kb"

#### GET /candidates/{email}
**Response extended with new optional fields**:
```json
{
  "email": "john@example.com",
  "name": "John Doe",
  // ... existing fields ...
  
  // NEW: Optional Zoho-specific fields
  "zoho_submission_id": "zoho_sub_xyz",
  "zoho_form_id": "zoho_form_123",
  "data_sources": {
    "current_title": ["zoho"],
    "skills": ["zoho", "resume"],
    "employment_history": ["resume"]
  },
  "source_name": "zoho_forms"  // "local_kb" or "zoho_forms"
}
```

#### GET /candidates/imports
**Response schema unchanged**
- Continues to list all in-flight imports
- New imports will have source_name="zoho_forms"

### 2. New API Endpoint

#### POST /candidates/import-from-zoho-form

**Purpose**: Import candidate from Zoho Form submission

**Request**:
```json
{
  "submission_id": "zoho_sub_xyz",
  "form_id": "zoho_form_123",
  "merge_strategy": "zoho_priority"  // optional, defaults to "standard"
}
```

**Response** (202 Accepted):
```json
{
  "import_id": "import_123",
  "status": "PROCESSING",
  "message": "Zoho form import queued for processing",
  "candidate_email": "john@example.com",
  "conflict": false,
  "zoho_submission_id": "zoho_sub_xyz"
}
```

**Error Responses**:
```json
// 404 if submission not found
{
  "detail": "Zoho submission zoho_sub_xyz not found"
}

// 422 if resume not attached
{
  "detail": "No resume file attached to this form submission"
}

// 400 if required fields missing
{
  "detail": "Form submission missing required fields: email, name"
}
```

**Background Processing**:
- Fetch Zoho submission data
- Download resume file
- Extract resume text
- Extract via LLM
- Merge data
- Check for conflicts
- Create/update candidate
- Generate embeddings
- Return to caller via webhook/polling

### 3. Updated Response Schemas

#### CandidateResponse (Extended)

```python
class ZohoSourceMetadata(BaseModel):
    zoho_submission_id: str | None = None
    zoho_form_id: str | None = None
    field_sources: dict[str, str] | None = None  # field → primary_source

class CandidateResponse(BaseModel):
    # ... existing fields ...
    
    # NEW: Zoho integration fields
    zoho_submission_id: str | None = None
    zoho_form_id: str | None = None
    data_sources: dict[str, list[str]] = Field(default_factory=dict)  
    # data_sources[field] = ["zoho", "resume"]
    source_name: str = "local_kb"  # "local_kb" | "zoho_forms" | ...
```

#### CandidateImportResponse (Extended)

```python
class CandidateImportResponse(BaseModel):
    # ... existing fields ...
    
    # NEW: Zoho metadata
    zoho_submission_id: str | None = None
    zoho_form_id: str | None = None
    merge_strategy: str | None = None
```

---

## Data Model Changes

### 1. Candidate Model Additions (`hr_agent/models/candidate.py`)

```python
class Candidate(Base):
    __tablename__ = "candidates"
    
    # ... existing fields ...
    
    # NEW: Zoho integration fields
    zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True)
    zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Track which source provided each field
    # Format: {"field_name": ["zoho", "resume"]}
    data_source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Timestamp when data was last synced from Zoho (for updates)
    last_zoho_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### 2. CandidateImport Model Additions (`hr_agent/models/candidate_import.py`)

```python
class CandidateImport(Base):
    __tablename__ = "candidate_imports"
    
    # ... existing fields ...
    
    # NEW: Zoho metadata
    zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True)
    zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Store Zoho form data for merge process
    zoho_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Merge strategy used
    merge_strategy: Mapped[str] = mapped_column(String, default="standard")
```

### 3. Database Migration

```sql
ALTER TABLE candidates ADD COLUMN zoho_submission_id VARCHAR;
ALTER TABLE candidates ADD COLUMN zoho_form_id VARCHAR;
ALTER TABLE candidates ADD COLUMN data_source_metadata JSON;
ALTER TABLE candidates ADD COLUMN last_zoho_sync TIMESTAMP;

ALTER TABLE candidate_imports ADD COLUMN zoho_submission_id VARCHAR;
ALTER TABLE candidate_imports ADD COLUMN zoho_form_id VARCHAR;
ALTER TABLE candidate_imports ADD COLUMN zoho_data JSON;
ALTER TABLE candidate_imports ADD COLUMN merge_strategy VARCHAR DEFAULT 'standard';

CREATE INDEX idx_candidates_zoho_submission_id ON candidates(zoho_submission_id);
CREATE INDEX idx_candidate_imports_zoho_submission_id ON candidate_imports(zoho_submission_id);
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

#### 1.1 Create Zoho Forms Client
- **File**: `hr_agent/services/zoho/forms_client.py`
- **Tasks**:
  - Define FormSubmission data structure
  - Implement form submission fetching
  - Implement resume file downloading
  - Add error handling & logging
  - Implement retry logic

#### 1.2 Create Candidate Merge Service
- **File**: `hr_agent/services/candidate_merge_service.py`
- **Tasks**:
  - Define MergeStrategy enum
  - Implement field-level merge logic
  - Define precedence rules
  - Track data sources
  - Handle validation

#### 1.3 Update Models
- **Files**: 
  - `hr_agent/models/candidate.py`
  - `hr_agent/models/candidate_import.py`
- **Tasks**:
  - Add new columns
  - Create Alembic migration
  - Update relationships if needed

### Phase 2: Integration (Week 2)

#### 2.1 Create API Endpoint
- **File**: `hr_agent/api/candidates.py`
- **Tasks**:
  - Add POST /candidates/import-from-zoho-form
  - Implement request validation
  - Hook to background task
  - Return appropriate responses

#### 2.2 Update Candidate Service
- **File**: `hr_agent/services/candidate_service.py`
- **Tasks**:
  - Add apply_merge_to_candidate() function
  - Extend apply_extraction_to_candidate() if needed
  - Handle source metadata tracking

#### 2.3 Update Background Processing
- **File**: `hr_agent/api/candidates.py` (_process_import function)
- **Tasks**:
  - Detect import type (resume vs Zoho form)
  - Branch logic for Zoho processing
  - Call merge service when needed
  - Maintain conflict resolution logic

### Phase 3: Schema & Testing (Week 3)

#### 3.1 Update Schemas
- **File**: `hr_agent/schemas/candidate.py`
- **Tasks**:
  - Add ZohoFormData schema
  - Add MergedCandidateData schema
  - Extend CandidateResponse
  - Extend CandidateImportResponse

#### 3.2 Create Tests
- **File**: `tests/test_zoho_forms_integration.py`
- **Tests**:
  - Merge logic (all scenarios)
  - API endpoint validation
  - Background task processing
  - Conflict detection
  - Data source tracking

#### 3.3 Integration Tests
- **File**: `tests/test_zoho_forms_e2e.py`
- **Tests**:
  - End-to-end form import
  - Field mapping verification
  - Existing resume upload still works
  - Domain classification with merged data

### Phase 4: Documentation & Deployment (Week 4)

#### 4.1 Documentation
- Update API spec
- Update architecture diagram
- Document merge rules
- Add troubleshooting guide

#### 4.2 Configuration
- Add Zoho forms specific settings
- Update .env template
- Document required OAuth scopes

#### 4.3 Deployment
- Create migration runner script
- Update deployment docs
- Plan gradual rollout
- Create monitoring alerts

---

## File-by-File Implementation

### New Files to Create

#### 1. `hr_agent/services/zoho/forms_client.py`

```python
"""
Zoho Forms client for fetching form submissions and downloading attachments.
"""

import logging
import requests
from typing import Any

from hr_agent.config import get_settings
from hr_agent.services.zoho.auth import ZohoAuthManager

logger = logging.getLogger(__name__)

class FormSubmission:
    """Represents a Zoho form submission."""
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.form_id = data.get("form_id")
        self.fields = data.get("fields", {})
        self.created_at = data.get("created_time")
        self.attachments = data.get("attachments", [])

class ZohoFormsClient:
    """Client for Zoho Forms API."""
    
    def __init__(self):
        self.settings = get_settings()
        self.auth_manager = ZohoAuthManager()
        tld = self.settings.zoho_dc.split(".")[-1]
        self.base_url = f"https://forms.zoho.{tld}/api/v2"
    
    def get_form_submission(self, form_id: str, submission_id: str) -> FormSubmission:
        """Fetch a specific form submission."""
        # Implementation
        pass
    
    def download_file(self, file_id: str) -> bytes:
        """Download a file attachment."""
        # Implementation
        pass
    
    def get_submission_files(self, submission_id: str) -> list[dict]:
        """Get all files attached to a submission."""
        # Implementation
        pass
```

#### 2. `hr_agent/services/candidate_merge_service.py`

```python
"""
Service for merging Zoho form data with LLM-extracted resume data.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MergeStrategy(StrEnum):
    STANDARD = "standard"  # Zoho for structured, resume for rich fields
    RESUME_PRIORITY = "resume_priority"  # Resume takes precedence
    ZOHO_PRIORITY = "zoho_priority"  # Zoho takes precedence

@dataclass
class ZohoFormData:
    """Structured data from Zoho form submission."""
    name: str | None = None
    email: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    skills: list[str] = field(default_factory=list)
    years_experience: int | None = None
    # ... other fields

@dataclass
class MergedCandidateData:
    """Result of merging Zoho + extracted data."""
    # All candidate fields
    name: str | None = None
    email: str | None = None
    # ... fields ...
    data_sources: dict[str, list[str]] = field(default_factory=dict)
    
    def get_field_sources(self, field_name: str) -> list[str]:
        """Which sources provided this field's value."""
        return self.data_sources.get(field_name, [])

class CandidateMergeService:
    """Intelligently merge Zoho form data + resume extraction."""
    
    def merge_sources(
        self,
        zoho_data: ZohoFormData,
        extracted: "CVExtracted",  # from schemas
        merge_strategy: MergeStrategy = MergeStrategy.STANDARD,
    ) -> MergedCandidateData:
        """
        Merge two data sources according to strategy.
        
        Args:
            zoho_data: Structured form data from Zoho
            extracted: Extracted data from resume via LLM
            merge_strategy: How to handle conflicts
        
        Returns:
            MergedCandidateData with all fields + source tracking
        """
        # Implementation with merge logic
        pass
    
    def _merge_field_string(
        self,
        field_name: str,
        zoho_value: str | None,
        extracted_value: str | None,
        strategy: MergeStrategy,
    ) -> tuple[str | None, list[str]]:
        """Merge a string field, return (value, sources)."""
        # Implementation
        pass
    
    def _merge_field_list(
        self,
        field_name: str,
        zoho_value: list[str],
        extracted_value: list[str],
        strategy: MergeStrategy,
    ) -> tuple[list[str], list[str]]:
        """Merge a list field, return (value, sources)."""
        # Implementation (union by default)
        pass
```

#### 3. `hr_agent/schemas/candidate.py` (Extensions)

```python
# Add to existing file:

class ZohoFormData(BaseModel):
    """Structured data from Zoho form submission."""
    submission_id: str
    form_id: str
    name: str | None = None
    email: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    seniority_level: str | None = None
    certifications: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    summary: str | None = None

class ZohoFormImportRequest(BaseModel):
    """Request to import candidate from Zoho form."""
    submission_id: str
    form_id: str
    merge_strategy: Literal["standard", "resume_priority", "zoho_priority"] = "standard"

# Extend CandidateResponse:
class CandidateResponse(BaseModel):
    # ... existing fields ...
    
    # NEW: Zoho integration
    zoho_submission_id: str | None = None
    zoho_form_id: str | None = None
    data_sources: dict[str, list[str]] = Field(default_factory=dict)
    source_name: str = "local_kb"  # Track source
```

### Modified Files

#### 1. `hr_agent/models/candidate.py`

```python
# Add to Candidate class:
zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True)
zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)
data_source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
last_zoho_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

#### 2. `hr_agent/models/candidate_import.py`

```python
# Add to CandidateImport class:
zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True)
zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)
zoho_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
merge_strategy: Mapped[str] = mapped_column(String, default="standard")
```

#### 3. `hr_agent/services/candidate_service.py`

```python
# Add new function:
def apply_merge_to_candidate(
    candidate: Candidate,
    merged_data: "MergedCandidateData",
    zoho_submission_id: str,
    zoho_form_id: str,
) -> None:
    """Apply merged Zoho + extracted data to candidate record."""
    # Copy merged data
    candidate.name = merged_data.name
    candidate.current_title = merged_data.current_title
    # ... all fields ...
    
    # Track sources
    candidate.data_source_metadata = merged_data.data_sources
    candidate.zoho_submission_id = zoho_submission_id
    candidate.zoho_form_id = zoho_form_id
    candidate.last_zoho_sync = datetime.utcnow()
```

#### 4. `hr_agent/api/candidates.py`

```python
# Add new endpoint:
@router.post("/import-from-zoho-form", response_model=CandidateUploadResponse, status_code=202)
async def import_candidate_from_zoho_form(
    payload: ZohoFormImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    extraction_svc: ExtractionService = Depends(get_extraction_service),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
):
    """Import candidate from Zoho form submission."""
    # Implementation
    pass

# Update _process_import to handle Zoho:
def _process_import(
    import_id: str,
    extraction_svc: ExtractionService,
    embedding_svc: EmbeddingService,
) -> None:
    """Background task: Enhanced to handle both resume and Zoho imports."""
    # Detect import type
    # Branch to appropriate processing
    # Apply merge if Zoho
```

---

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Zoho API rate limiting | Medium | Medium | Implement backoff & queuing |
| Resume download fails | Low | High | Fallback to form data; logging |
| Merge conflicts create bad data | Medium | High | Comprehensive validation; audit trail |
| Email conflicts with Zoho | Medium | Medium | Existing conflict resolution handles |
| Performance impact (extra API call) | Medium | Low | Async processing; caching |

### Data Risks

| Risk | Mitigation |
|------|-----------|
| Stale Zoho data | Add last_zoho_sync timestamp; re-fetch option |
| Duplicate merging | Email deduplication works same as before |
| Lost data during merge | Track all sources; store original Zoho data |
| Inconsistent field mapping | Document mapping; unit tests |

### Operational Risks

| Risk | Mitigation |
|------|-----------|
| Zoho service outage | Graceful degradation; fallback to resume only |
| OAuth token expiration | ZohoAuthManager handles refresh |
| Database migration fails | Test migration in staging first |
| Backward compatibility | All changes are additive/optional |

---

## Edge Cases & Handling

### 1. Resume Not Attached to Form
**Scenario**: Zoho form submitted but no resume file
**Handling**: 
- Return error: "No resume file attached"
- Optionally: Use Zoho form data only (manual confirmation)

### 2. Email Mismatch (Zoho ≠ Resume)
**Scenario**: Form has john@company.com, resume has john@gmail.com
**Handling**:
- Use email from resume (primary key)
- Log discrepancy
- Track both in metadata

### 3. Zoho Data Missing Required Fields
**Scenario**: Form missing email or name
**Handling**:
- Extraction from resume fills gaps
- If resume also missing → fail gracefully

### 4. Very Large Candidate Name
**Scenario**: Zoho form has middle names not in resume
**Handling**:
- Merge: Use Zoho (more complete usually)
- Fall back to resume if Zoho name suspicious

### 5. Conflict Resolution
**Scenario**: Candidate with email already exists
**Handling**:
- Same as existing: Show conflict UI
- Allow user to update or keep
- Merge applies only on update action

### 6. Skills Deduplication
**Scenario**: Zoho has "Python", resume has "python"
**Handling**:
- Normalize to lowercase before union
- Remove exact duplicates

---

## Testing Strategy

### Unit Tests

#### Test Files
- `tests/test_candidate_merge_service.py` - Merge logic
- `tests/test_zoho_forms_client.py` - API client
- `tests/test_zoho_import_endpoint.py` - Endpoint validation

#### Key Test Cases

```python
# Merge service tests
test_merge_zoho_priority_strategy()
test_merge_resume_priority_strategy()
test_merge_union_strategy_for_skills()
test_merge_empty_zoho_field()
test_merge_empty_resume_field()
test_merge_conflicting_values()
test_merge_data_source_tracking()

# API endpoint tests
test_import_zoho_form_success()
test_import_zoho_form_missing_resume()
test_import_zoho_form_invalid_submission_id()
test_import_zoho_form_invalid_merge_strategy()

# Client tests
test_fetch_form_submission_success()
test_fetch_form_submission_not_found()
test_download_resume_file_success()
test_download_resume_file_not_found()
```

### Integration Tests

```python
test_end_to_end_zoho_import()
test_zoho_import_creates_candidate()
test_zoho_import_triggers_domain_classification()
test_zoho_import_generates_embeddings()
test_zoho_import_with_conflict()
test_zoho_import_with_existing_resume_upload()
```

### Load Testing

```python
test_concurrent_zoho_imports()
test_rate_limiting_handling()
test_database_migration_on_large_dataset()
```

### Regression Testing

```python
test_existing_resume_upload_still_works()
test_existing_conflict_resolution_still_works()
test_existing_domain_classification_still_works()
test_existing_embedding_generation_still_works()
```

---

## Configuration & Environment Variables

### New Environment Variables

```bash
# Zoho Forms specific settings
ZOHO_FORMS_ENABLED=true
ZOHO_FORMS_API_KEY=xxx  # If using API key instead of OAuth
ZOHO_FORMS_OWNER_ID=xxx  # Zoho form owner/workspace ID
ZOHO_FORMS_DEFAULT_MERGE_STRATEGY=standard

# Existing but used for forms
ZOHO_CLIENT_ID=xxx
ZOHO_CLIENT_SECRET=xxx
ZOHO_REDIRECT_URI=xxx
ZOHO_DC=accounts.zoho.in
```

### Configuration File Updates

```python
# hr_agent/config.py
@dataclass
class Settings:
    # ... existing ...
    
    # Zoho Forms
    zoho_forms_enabled: bool = False
    zoho_forms_default_merge_strategy: str = "standard"
    zoho_forms_max_file_size_mb: int = 50
    zoho_forms_supported_extensions: list[str] = ["pdf"]
```

---

## Rollback Strategy

### Step 1: Pre-Deployment Verification
- [ ] All tests passing (unit + integration + regression)
- [ ] Database migration tested on staging
- [ ] Canary test with 1% traffic
- [ ] Monitor error rates

### Step 2: Gradual Rollout
- [ ] Enable for internal users only (10% traffic)
- [ ] Monitor for 24 hours
- [ ] Enable for beta users (50% traffic)
- [ ] Monitor for 48 hours
- [ ] Full release (100% traffic)

### Step 3: Rollback Plan
- [ ] Disable Zoho endpoint (set `zoho_forms_enabled=false`)
- [ ] Retain all data (database changes are non-destructive)
- [ ] Existing imports unaffected
- [ ] Revert API changes if needed

### Database Rollback
```sql
-- If needed, add columns to candidate table can be safely reverted:
-- (Just don't use them; no data loss)
ALTER TABLE candidates DROP COLUMN zoho_submission_id;
ALTER TABLE candidates DROP COLUMN zoho_form_id;
ALTER TABLE candidates DROP COLUMN data_source_metadata;
ALTER TABLE candidates DROP COLUMN last_zoho_sync;
```

---

## Performance Considerations

### Optimization Strategies

1. **Caching**: Cache Zoho form metadata (schema, fields)
2. **Async**: Background task for processing (already in place)
3. **Batch Processing**: Bulk import support in future
4. **Rate Limiting**: Respect Zoho API limits
5. **Database Indexes**: Index zoho_submission_id for lookups

### Monitoring

```python
# Metrics to track
- zoho_import_count (daily, hourly)
- zoho_import_duration (avg, p95, p99)
- merge_conflict_rate (%)
- resume_download_failures (%)
- api_error_rate_by_error_type
```

---

## Security Considerations

### Authentication & Authorization

1. **OAuth**: Use existing ZohoAuthManager
2. **Scope**: Request `forms:read` scope minimum
3. **Token Refresh**: Automatic via auth manager
4. **Rate Limiting**: Prevent abuse of Zoho API

### Data Protection

1. **Encryption**: Resume files encrypted in transit (HTTPS)
2. **Validation**: Validate all Zoho data before DB write
3. **Audit**: Log all imports with user context
4. **GDPR**: Support data deletion requests

---

## Success Metrics

### Functional Success
- [ ] Zoho forms successfully import candidates
- [ ] Merge logic works correctly for all field combinations
- [ ] Existing resume upload still works (100% backward compatible)
- [ ] Conflict resolution works for Zoho imports
- [ ] Domain classification works on merged data

### Performance Success
- [ ] Zoho import completes in < 30 seconds
- [ ] No degradation to existing resume upload speed
- [ ] Database queries < 100ms for candidate retrieval
- [ ] Background task processing < 5 minutes per import

### Quality Success
- [ ] Zero data loss during merge
- [ ] 100% of merge tests passing
- [ ] Zero breaking changes to existing APIs
- [ ] All regression tests passing

---

## Next Steps

1. **Confirm Zoho API**: Verify form field names and attachment API
2. **Finalize Mapping**: Lock in exact Zoho field → candidate field mapping
3. **Create Migration**: Design and test database migration
4. **Implementation Sprint**: Execute Phase 1-4 plan
5. **Staging Validation**: Full end-to-end testing
6. **Production Rollout**: Gradual rollout with monitoring

