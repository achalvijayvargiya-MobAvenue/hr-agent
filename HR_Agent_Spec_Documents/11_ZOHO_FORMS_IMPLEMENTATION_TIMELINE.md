# Zoho Forms Integration - Implementation Timeline

**Document**: Detailed day-by-day implementation plan with code samples  
**Status**: Ready for implementation  
**Estimated Duration**: 20 working days (4 weeks)

---

## Week 1: Foundation & Core Services

### Day 1-2: Zoho Forms Client

#### Task: Implement `hr_agent/services/zoho/forms_client.py`

```python
"""
Zoho Forms client for fetching form submissions and downloading attachments.

API Reference: https://www.zoho.com/forms/help/api-reference/
"""

import logging
import tempfile
import os
from typing import Any, List
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from hr_agent.config import get_settings
from hr_agent.services.zoho.auth import ZohoAuthManager

logger = logging.getLogger(__name__)


class FormSubmission:
    """Represents a Zoho form submission with metadata and attachments."""
    
    def __init__(self, data: dict[str, Any]):
        self._data = data
        self.id = data.get("id")
        self.form_id = data.get("form_id")
        self.created_at = data.get("created_time")
        self.form_owner = data.get("form_owner")
    
    @property
    def fields(self) -> dict[str, Any]:
        """Get form field values."""
        return self._data.get("fields", {})
    
    @property
    def attachments(self) -> list[dict[str, Any]]:
        """Get file attachments (resumes, etc)."""
        return self._data.get("attachments", [])
    
    def get_field_value(self, field_name: str, default: Any = None) -> Any:
        """Get a single field value by name."""
        return self.fields.get(field_name, default)
    
    def get_resume_attachment(self) -> dict[str, Any] | None:
        """Find and return the first PDF attachment (assumed to be resume)."""
        for att in self.attachments:
            if att.get("file_name", "").lower().endswith(".pdf"):
                return att
        return None
    
    def __repr__(self) -> str:
        return f"<FormSubmission id={self.id!r} form_id={self.form_id!r}>"


class ZohoFormsClient:
    """Client for Zoho Forms API with retry logic and error handling."""
    
    def __init__(self):
        self.settings = get_settings()
        self.auth_manager = ZohoAuthManager()
        
        # Extract TLD from settings (e.g., accounts.zoho.in → zoho.in)
        tld = self.settings.zoho_dc.split(".")[-1]
        self.base_url = f"https://forms.zoho.{tld}/api/v2"
        
        self.session = self._create_retry_session()
        logger.debug(f"[ZOHO:FORMS] Client initialized — base_url={self.base_url}")
    
    def _create_retry_session(self) -> requests.Session:
        """Create a session with retry strategy for rate limits and server errors."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers with valid access token."""
        token = self.auth_manager.get_valid_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json",
        }
    
    def get_form_submission(self, form_id: str, submission_id: str) -> FormSubmission:
        """
        Fetch a specific form submission by ID.
        
        Args:
            form_id: Zoho form ID
            submission_id: Zoho submission ID
        
        Returns:
            FormSubmission object
        
        Raises:
            requests.RequestException: On network error
            ValueError: If submission not found or invalid response
        """
        url = f"{self.base_url}/forms/{form_id}/submissions/{submission_id}"
        headers = self._get_headers()
        
        logger.info(f"[ZOHO:FORMS] Fetching submission — form_id={form_id} submission_id={submission_id}")
        
        try:
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error(f"[ZOHO:FORMS] Request timeout for {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[ZOHO:FORMS] Request failed: {e}")
            raise
        
        data = response.json()
        
        if data.get("code") != 0:  # Zoho returns code=0 for success
            error_msg = data.get("message", "Unknown error")
            logger.error(f"[ZOHO:FORMS] API error — {error_msg}")
            raise ValueError(f"Zoho API error: {error_msg}")
        
        submission_data = data.get("data", {})
        logger.info(f"[ZOHO:FORMS] Submission fetched ✓ — id={submission_data.get('id')}")
        
        return FormSubmission(submission_data)
    
    def list_form_submissions(
        self, form_id: str, limit: int = 100, from_index: int = 0
    ) -> tuple[list[FormSubmission], int]:
        """
        List all submissions for a form (paginated).
        
        Args:
            form_id: Zoho form ID
            limit: Maximum results per page (max 100)
            from_index: Pagination index
        
        Returns:
            (list of FormSubmission, total_count)
        """
        url = f"{self.base_url}/forms/{form_id}/submissions"
        headers = self._get_headers()
        params = {"limit": min(limit, 100), "from": from_index}
        
        logger.info(f"[ZOHO:FORMS] Listing submissions — form_id={form_id} limit={limit}")
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[ZOHO:FORMS] Request failed: {e}")
            raise
        
        data = response.json()
        if data.get("code") != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error(f"[ZOHO:FORMS] API error — {error_msg}")
            raise ValueError(f"Zoho API error: {error_msg}")
        
        submissions = [
            FormSubmission(sub) for sub in data.get("data", [])
        ]
        total = data.get("page_context", {}).get("total_count", 0)
        
        logger.info(f"[ZOHO:FORMS] Fetched {len(submissions)} submissions (total: {total})")
        
        return submissions, total
    
    def download_file(self, form_id: str, submission_id: str, file_id: str) -> bytes:
        """
        Download a file attachment from a form submission.
        
        Args:
            form_id: Zoho form ID
            submission_id: Submission ID
            file_id: File ID of attachment
        
        Returns:
            File bytes
        
        Raises:
            ValueError: If file not found or invalid
        """
        url = f"{self.base_url}/forms/{form_id}/submissions/{submission_id}/attachments/{file_id}"
        headers = self._get_headers()
        
        logger.info(f"[ZOHO:FORMS] Downloading file — file_id={file_id}")
        
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            logger.info(f"[ZOHO:FORMS] File downloaded ✓ — size={len(response.content)} bytes")
            return response.content
        
        except requests.exceptions.Timeout:
            logger.error(f"[ZOHO:FORMS] Download timeout for file {file_id}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[ZOHO:FORMS] Download failed: {e}")
            raise
    
    def validate_submission_has_required_fields(
        self, submission: FormSubmission, required_fields: list[str]
    ) -> tuple[bool, list[str]]:
        """
        Validate that a submission has all required fields populated.
        
        Args:
            submission: FormSubmission object
            required_fields: List of field names to check
        
        Returns:
            (is_valid, list_of_missing_fields)
        """
        missing = []
        for field_name in required_fields:
            value = submission.get_field_value(field_name)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(field_name)
        
        is_valid = len(missing) == 0
        if not is_valid:
            logger.warning(f"[ZOHO:FORMS] Submission missing fields: {missing}")
        
        return is_valid, missing
    
    def validate_submission_has_resume(self, submission: FormSubmission) -> bool:
        """
        Check if submission has a PDF resume attached.
        
        Args:
            submission: FormSubmission object
        
        Returns:
            True if at least one PDF attachment found
        """
        has_resume = submission.get_resume_attachment() is not None
        if not has_resume:
            logger.warning(f"[ZOHO:FORMS] Submission {submission.id} has no resume attachment")
        return has_resume
```

#### Testing: `tests/test_zoho_forms_client.py`

```python
import pytest
from unittest.mock import patch, MagicMock

from hr_agent.services.zoho.forms_client import ZohoFormsClient, FormSubmission


@pytest.fixture
def zoho_client():
    with patch("hr_agent.services.zoho.forms_client.ZohoAuthManager"):
        return ZohoFormsClient()


def test_form_submission_get_field_value(zoho_client):
    data = {
        "id": "sub_123",
        "form_id": "form_456",
        "fields": {
            "email": "john@example.com",
            "name": "John Doe",
        },
        "attachments": [],
    }
    submission = FormSubmission(data)
    
    assert submission.get_field_value("email") == "john@example.com"
    assert submission.get_field_value("missing", "default") == "default"


def test_form_submission_get_resume_attachment():
    data = {
        "id": "sub_123",
        "form_id": "form_456",
        "fields": {},
        "attachments": [
            {"id": "att_1", "file_name": "resume.pdf"},
            {"id": "att_2", "file_name": "photo.jpg"},
        ],
    }
    submission = FormSubmission(data)
    
    resume = submission.get_resume_attachment()
    assert resume is not None
    assert resume["id"] == "att_1"
    assert resume["file_name"] == "resume.pdf"


@patch("hr_agent.services.zoho.forms_client.ZohoFormsClient.session")
def test_get_form_submission_success(mock_session, zoho_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "id": "sub_123",
            "form_id": "form_456",
            "fields": {"email": "john@example.com"},
            "attachments": [],
        },
    }
    mock_session.get.return_value = mock_response
    
    submission = zoho_client.get_form_submission("form_456", "sub_123")
    assert submission.id == "sub_123"
    assert submission.get_field_value("email") == "john@example.com"


def test_validate_submission_has_required_fields():
    data = {
        "id": "sub_123",
        "form_id": "form_456",
        "fields": {
            "email": "john@example.com",
            "name": "John Doe",
        },
        "attachments": [],
    }
    submission = FormSubmission(data)
    
    is_valid, missing = ZohoFormsClient.validate_submission_has_required_fields(
        submission, ["email", "name"]
    )
    assert is_valid is True
    assert missing == []
    
    # Test with missing field
    is_valid, missing = ZohoFormsClient.validate_submission_has_required_fields(
        submission, ["email", "name", "phone"]
    )
    assert is_valid is False
    assert "phone" in missing
```

---

### Day 3-4: Candidate Merge Service

#### Task: Implement `hr_agent/services/candidate_merge_service.py`

```python
"""
Service for intelligently merging Zoho form data with LLM-extracted resume data.
"""

import logging
from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any, Optional

from hr_agent.schemas.candidate import CVExtracted

logger = logging.getLogger(__name__)


class MergeStrategy(StrEnum):
    """Strategy for resolving field conflicts."""
    
    STANDARD = "standard"  # Zoho for structured, resume for rich fields
    RESUME_PRIORITY = "resume_priority"  # Resume takes precedence
    ZOHO_PRIORITY = "zoho_priority"  # Zoho takes precedence


@dataclass
class ZohoFormData:
    """Structured data extracted from Zoho form submission."""
    
    name: Optional[str] = None
    email: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    years_experience: Optional[int] = None
    seniority_level: Optional[str] = None
    certifications: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    summary: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, filtering out None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MergedCandidateData:
    """Result of merging Zoho form data + resume extraction."""
    
    # Core fields
    name: Optional[str] = None
    email: Optional[str] = None
    current_title: Optional[str] = None
    normalized_role: Optional[str] = None
    years_experience: Optional[float] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    
    # Lists
    skills: list[str] = field(default_factory=list)
    tools_and_technologies: list[str] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    employment_history: list[dict] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    experience_areas: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    
    # Metadata
    seniority_level: Optional[str] = None
    summary: Optional[str] = None
    
    # Data source tracking: field_name → ["zoho", "resume"]
    data_sources: dict[str, list[str]] = field(default_factory=dict)
    
    def get_field_sources(self, field_name: str) -> list[str]:
        """Which sources provided this field's value."""
        return self.data_sources.get(field_name, [])
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v not in (None, [], {})}


class CandidateMergeService:
    """Intelligently merge Zoho form data with resume extraction."""
    
    # Field merge preferences
    MERGE_PREFERENCES = {
        # ZOHO_PRIORITY: Use Zoho first, fallback to resume
        "zoho_priority": [
            "name",
            "current_title",
            "current_company",
            "location",
            "seniority_level",
            "years_experience",
        ],
        # RESUME_PRIORITY: Use resume first
        "resume_priority": [
            "normalized_role",
            "education",
            "employment_history",
            "tools_and_technologies",
            "experience_areas",
            "responsibilities",
        ],
        # UNION: Combine both (remove duplicates)
        "union": [
            "skills",
            "certifications",
            "industries",
        ],
        # RESUME_ONLY: Ignore Zoho, use resume
        "resume_only": [
            "education",
            "employment_history",
            "tools_and_technologies",
            "experience_areas",
            "responsibilities",
        ],
    }
    
    def merge_sources(
        self,
        zoho_data: ZohoFormData,
        extracted: CVExtracted,
        merge_strategy: MergeStrategy = MergeStrategy.STANDARD,
    ) -> MergedCandidateData:
        """
        Merge two data sources according to strategy.
        
        Args:
            zoho_data: Structured form data from Zoho
            extracted: Extracted data from resume via LLM
            merge_strategy: How to handle field conflicts
        
        Returns:
            MergedCandidateData with all fields + source tracking
        """
        logger.info(
            f"[MERGE] Starting merge — strategy={merge_strategy} "
            f"zoho_email={zoho_data.email} resume_email={extracted.email}"
        )
        
        merged = MergedCandidateData()
        
        # Email: Use from resume (primary key), fallback to Zoho
        merged.email, sources = self._merge_email(zoho_data.email, extracted.email)
        merged.data_sources["email"] = sources
        
        # Name: Prefer Zoho (more likely to be correct in form)
        merged.name, sources = self._merge_field_string(
            "name",
            zoho_data.name,
            extracted.candidate_name,
            merge_strategy,
        )
        merged.data_sources["name"] = sources
        
        # Current title: Prefer Zoho
        merged.current_title, sources = self._merge_field_string(
            "current_title",
            zoho_data.current_title,
            extracted.current_title,
            merge_strategy,
        )
        merged.data_sources["current_title"] = sources
        
        # Current company: Prefer Zoho
        merged.current_company, sources = self._merge_field_string(
            "current_company",
            zoho_data.current_company,
            extracted.current_company,
            merge_strategy,
        )
        merged.data_sources["current_company"] = sources
        
        # Location: Merge (use Zoho as primary)
        merged.location, sources = self._merge_field_string(
            "location",
            zoho_data.location,
            extracted.location,
            merge_strategy,
        )
        merged.data_sources["location"] = sources
        
        # Years experience: Prefer Zoho (if numeric)
        merged.years_experience, sources = self._merge_field_numeric(
            "years_experience",
            zoho_data.years_experience,
            extracted.years_experience,
            merge_strategy,
        )
        merged.data_sources["years_experience"] = sources
        
        # Seniority level: Prefer Zoho
        merged.seniority_level, sources = self._merge_field_string(
            "seniority_level",
            zoho_data.seniority_level,
            extracted.seniority_level,
            merge_strategy,
        )
        merged.data_sources["seniority_level"] = sources
        
        # Skills: Union strategy (combine both)
        merged.skills, sources = self._merge_field_list(
            "skills",
            zoho_data.skills,
            extracted.skills,
            "union",
        )
        merged.data_sources["skills"] = sources
        
        # Certifications: Union
        merged.certifications, sources = self._merge_field_list(
            "certifications",
            zoho_data.certifications,
            extracted.certifications,
            "union",
        )
        merged.data_sources["certifications"] = sources
        
        # Industries: Union
        merged.industries, sources = self._merge_field_list(
            "industries",
            zoho_data.industries,
            extracted.industries,
            "union",
        )
        merged.data_sources["industries"] = sources
        
        # Resume-only fields (always from extracted)
        merged.normalized_role = extracted.normalized_role
        merged.education = [e.model_dump() for e in extracted.education]
        merged.employment_history = [e.model_dump() for e in extracted.employment_history]
        merged.tools_and_technologies = extracted.tools_and_technologies
        merged.experience_areas = extracted.experience_areas
        merged.responsibilities = extracted.responsibilities
        
        merged.data_sources["normalized_role"] = ["resume"]
        merged.data_sources["education"] = ["resume"]
        merged.data_sources["employment_history"] = ["resume"]
        merged.data_sources["tools_and_technologies"] = ["resume"]
        merged.data_sources["experience_areas"] = ["resume"]
        merged.data_sources["responsibilities"] = ["resume"]
        
        # Summary: Prefer resume (usually more detailed)
        merged.summary, sources = self._merge_field_string(
            "summary",
            zoho_data.summary,
            extracted.summary,
            "resume_priority",
        )
        merged.data_sources["summary"] = sources
        
        logger.info(
            f"[MERGE] Merge complete ✓ — name={merged.name!r} email={merged.email!r} "
            f"skills_count={len(merged.skills)} sources_tracked={len(merged.data_sources)}"
        )
        
        return merged
    
    def _merge_email(
        self, zoho_email: Optional[str], resume_email: Optional[str]
    ) -> tuple[Optional[str], list[str]]:
        """Merge email: use from resume (primary key), fallback to Zoho."""
        if resume_email:
            return resume_email, ["resume"]
        return zoho_email, ["zoho"] if zoho_email else []
    
    def _merge_field_string(
        self,
        field_name: str,
        zoho_value: Optional[str],
        resume_value: Optional[str],
        strategy: MergeStrategy,
    ) -> tuple[Optional[str], list[str]]:
        """
        Merge a string field.
        
        Returns: (merged_value, sources)
        """
        # Normalize empty strings to None
        zoho_val = zoho_value.strip() if zoho_value else None
        resume_val = resume_value.strip() if resume_value else None
        
        # Both present: choose based on strategy
        if zoho_val and resume_val:
            if strategy == MergeStrategy.RESUME_PRIORITY:
                logger.debug(
                    f"[MERGE] Conflict on {field_name}: "
                    f"choosing resume='{resume_val}' over zoho='{zoho_val}'"
                )
                return resume_val, ["resume"]
            elif strategy == MergeStrategy.ZOHO_PRIORITY:
                logger.debug(
                    f"[MERGE] Conflict on {field_name}: "
                    f"choosing zoho='{zoho_val}' over resume='{resume_val}'"
                )
                return zoho_val, ["zoho"]
            else:  # STANDARD: prefer Zoho for structured fields
                return zoho_val, ["zoho"]
        
        # Only one present
        if zoho_val:
            return zoho_val, ["zoho"]
        if resume_val:
            return resume_val, ["resume"]
        
        return None, []
    
    def _merge_field_numeric(
        self,
        field_name: str,
        zoho_value: Optional[int],
        resume_value: Optional[float],
        strategy: MergeStrategy,
    ) -> tuple[Optional[float], list[str]]:
        """Merge a numeric field (years of experience)."""
        # Both present: prefer Zoho (usually more accurate in form)
        if zoho_value is not None and resume_value is not None:
            if strategy == MergeStrategy.RESUME_PRIORITY:
                return resume_value, ["resume"]
            else:
                # STANDARD or ZOHO_PRIORITY: use Zoho
                return float(zoho_value), ["zoho"]
        
        if zoho_value is not None:
            return float(zoho_value), ["zoho"]
        if resume_value is not None:
            return resume_value, ["resume"]
        
        return None, []
    
    def _merge_field_list(
        self,
        field_name: str,
        zoho_values: list[str],
        resume_values: list[str],
        merge_mode: str = "union",
    ) -> tuple[list[str], list[str]]:
        """
        Merge a list field.
        
        Args:
            merge_mode: "union" (combine), "resume_priority", "zoho_priority"
        
        Returns: (merged_list, sources)
        """
        zoho_clean = [v.strip().lower() for v in zoho_values if v and v.strip()]
        resume_clean = [v.strip().lower() for v in resume_values if v and v.strip()]
        
        if merge_mode == "union":
            # Combine and deduplicate
            combined = list(set(zoho_clean + resume_clean))
            sources = []
            if zoho_clean:
                sources.append("zoho")
            if resume_clean:
                sources.append("resume")
            
            logger.debug(
                f"[MERGE] Union on {field_name}: "
                f"zoho_count={len(zoho_clean)} resume_count={len(resume_clean)} "
                f"merged_count={len(combined)}"
            )
            
            return sorted(combined), sources
        
        elif merge_mode == "resume_priority":
            if resume_values:
                return resume_clean, ["resume"]
            return zoho_clean, ["zoho"] if zoho_clean else []
        
        else:  # ZOHO_PRIORITY
            if zoho_values:
                return zoho_clean, ["zoho"]
            return resume_clean, ["resume"] if resume_clean else []
```

#### Testing: `tests/test_candidate_merge_service.py`

```python
import pytest

from hr_agent.services.candidate_merge_service import (
    CandidateMergeService,
    ZohoFormData,
    MergedCandidateData,
    MergeStrategy,
)
from hr_agent.schemas.candidate import CVExtracted, EducationEntry, EmploymentHistoryEntry


@pytest.fixture
def merge_service():
    return CandidateMergeService()


def test_merge_string_field_both_present_standard_strategy(merge_service):
    zoho_data = ZohoFormData(name="John Zoho")
    extracted = CVExtracted(candidate_name="John Resume", summary="test")
    
    result, sources = merge_service._merge_field_string(
        "name", "John Zoho", "John Resume", MergeStrategy.STANDARD
    )
    
    # STANDARD prefers Zoho for structured fields
    assert result == "John Zoho"
    assert "zoho" in sources


def test_merge_string_field_both_present_resume_priority(merge_service):
    result, sources = merge_service._merge_field_string(
        "education", "HS", "Bachelor's", MergeStrategy.RESUME_PRIORITY
    )
    
    assert result == "Bachelor's"
    assert "resume" in sources


def test_merge_string_field_only_zoho(merge_service):
    result, sources = merge_service._merge_field_string(
        "current_company", "Acme Corp", None, MergeStrategy.STANDARD
    )
    
    assert result == "Acme Corp"
    assert sources == ["zoho"]


def test_merge_string_field_only_resume(merge_service):
    result, sources = merge_service._merge_field_string(
        "current_title", None, "Senior Engineer", MergeStrategy.STANDARD
    )
    
    assert result == "Senior Engineer"
    assert sources == ["resume"]


def test_merge_string_field_both_empty(merge_service):
    result, sources = merge_service._merge_field_string(
        "location", None, None, MergeStrategy.STANDARD
    )
    
    assert result is None
    assert sources == []


def test_merge_field_list_union(merge_service):
    result, sources = merge_service._merge_field_list(
        "skills",
        ["Python", "JavaScript"],
        ["Python", "Go"],  # Python is duplicate
        merge_mode="union",
    )
    
    # Should deduplicate
    assert len(result) == 3
    assert "python" in result
    assert "javascript" in result
    assert "go" in result
    assert sorted(sources) == ["resume", "zoho"]


def test_merge_field_list_resume_priority(merge_service):
    result, sources = merge_service._merge_field_list(
        "skills",
        ["Python", "JavaScript"],
        ["Go", "Rust"],
        merge_mode="resume_priority",
    )
    
    assert result == ["go", "rust"]
    assert sources == ["resume"]


def test_full_merge_standard_strategy(merge_service):
    zoho_data = ZohoFormData(
        name="John Zoho",
        email="john.zoho@company.com",
        current_title="Senior Engineer",
        current_company="Acme Corp",
        location="New York",
        skills=["Python", "JavaScript"],
        years_experience=10,
        seniority_level="Senior",
        summary="Zoho bio",
    )
    
    extracted = CVExtracted(
        candidate_name="John Resume",
        email="john.resume@gmail.com",
        current_title="Staff Engineer",
        current_company="BigTech Inc",
        location="San Francisco",
        skills=["Python", "Go"],
        years_experience=12.0,
        seniority_level="Staff",
        summary="Long resume summary with lots of details",
        normalized_role="engineer",
        education=[],
        employment_history=[],
        tools_and_technologies=["Docker", "Kubernetes"],
        industries=["Tech"],
        experience_areas=["Backend"],
        responsibilities=["Architecture"],
        certifications=[],
    )
    
    merged = merge_service.merge_sources(
        zoho_data, extracted, MergeStrategy.STANDARD
    )
    
    # STANDARD strategy:
    # - name: Zoho
    # - email: Resume (primary key)
    # - current_title: Zoho
    # - years_experience: Zoho
    # - skills: Union
    
    assert merged.name == "John Zoho"
    assert merged.email == "john.resume@gmail.com"  # Resume
    assert merged.current_title == "Senior Engineer"  # Zoho
    assert merged.years_experience == 10.0  # Zoho
    assert "python" in merged.skills
    assert "go" in merged.skills
    assert "javascript" in merged.skills


def test_merge_tracks_data_sources(merge_service):
    zoho_data = ZohoFormData(name="John", skills=["Python"])
    extracted = CVExtracted(
        candidate_name="X",
        skills=["Go"],
        summary="test",
        normalized_role="eng",
    )
    
    merged = merge_service.merge_sources(zoho_data, extracted, MergeStrategy.STANDARD)
    
    assert merged.data_sources["name"] == ["zoho"]
    assert sorted(merged.data_sources["skills"]) == ["resume", "zoho"]
    assert merged.data_sources["normalized_role"] == ["resume"]
```

---

### Day 5: Database Models & Migration

#### Task: Update models

**File**: `hr_agent/models/candidate.py` (add fields)

```python
# Add to existing Candidate class:

zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)

# Track which source provided each field
# Format: {"current_title": ["zoho"], "skills": ["zoho", "resume"]}
data_source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# Timestamp for last Zoho sync
last_zoho_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**File**: `hr_agent/models/candidate_import.py` (add fields)

```python
# Add to existing CandidateImport class:

zoho_submission_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
zoho_form_id: Mapped[str | None] = mapped_column(String, nullable=True)

# Store Zoho form data for merge process
zoho_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# Merge strategy applied ("standard", "resume_priority", "zoho_priority")
merge_strategy: Mapped[str] = mapped_column(String, default="standard")
```

#### Task: Create Alembic migration

```bash
alembic revision --autogenerate -m "Add Zoho Forms integration fields"
```

**File**: `migrations/versions/xxxx_add_zoho_fields.py`

```python
"""Add Zoho Forms integration fields"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Add columns to candidates table
    op.add_column('candidates', sa.Column('zoho_submission_id', sa.String(), nullable=True))
    op.add_column('candidates', sa.Column('zoho_form_id', sa.String(), nullable=True))
    op.add_column('candidates', sa.Column('data_source_metadata', sa.JSON(), nullable=True))
    op.add_column('candidates', sa.Column('last_zoho_sync', sa.DateTime(), nullable=True))
    
    # Create index on zoho_submission_id for faster lookups
    op.create_index('ix_candidates_zoho_submission_id', 'candidates', ['zoho_submission_id'])
    
    # Add columns to candidate_imports table
    op.add_column('candidate_imports', sa.Column('zoho_submission_id', sa.String(), nullable=True))
    op.add_column('candidate_imports', sa.Column('zoho_form_id', sa.String(), nullable=True))
    op.add_column('candidate_imports', sa.Column('zoho_data', sa.JSON(), nullable=True))
    op.add_column('candidate_imports', sa.Column('merge_strategy', sa.String(), server_default='standard'))
    
    # Create index on zoho_submission_id for candidate_imports
    op.create_index('ix_candidate_imports_zoho_submission_id', 'candidate_imports', ['zoho_submission_id'])


def downgrade():
    op.drop_index('ix_candidate_imports_zoho_submission_id', table_name='candidate_imports')
    op.drop_column('candidate_imports', 'merge_strategy')
    op.drop_column('candidate_imports', 'zoho_data')
    op.drop_column('candidate_imports', 'zoho_form_id')
    op.drop_column('candidate_imports', 'zoho_submission_id')
    
    op.drop_index('ix_candidates_zoho_submission_id', table_name='candidates')
    op.drop_column('candidates', 'last_zoho_sync')
    op.drop_column('candidates', 'data_source_metadata')
    op.drop_column('candidates', 'zoho_form_id')
    op.drop_column('candidates', 'zoho_submission_id')
```

---

## Week 2: API Integration & Candidate Service

### Day 6-7: Extend Candidate Service

#### Task: Update `hr_agent/services/candidate_service.py`

```python
# Add new function after existing functions:

from datetime import datetime


def apply_merge_to_candidate(
    candidate: Candidate,
    merged_data: "MergedCandidateData",
    zoho_submission_id: str,
    zoho_form_id: str,
) -> None:
    """
    Apply merged Zoho + extracted data to candidate record.
    
    Args:
        candidate: Candidate ORM model to update
        merged_data: Result of merge_sources()
        zoho_submission_id: Zoho form submission ID
        zoho_form_id: Zoho form ID
    """
    # Apply all merged fields
    candidate.name = merged_data.name
    candidate.current_title = merged_data.current_title
    candidate.normalized_role = merged_data.normalized_role
    candidate.years_experience = merged_data.years_experience
    candidate.current_company = merged_data.current_company
    candidate.location = merged_data.location
    candidate.skills = merged_data.skills
    candidate.tools_and_technologies = merged_data.tools_and_technologies
    candidate.education = merged_data.education
    candidate.certifications = merged_data.certifications
    candidate.employment_history = merged_data.employment_history
    candidate.industries = merged_data.industries
    candidate.experience_areas = merged_data.experience_areas
    candidate.responsibilities = merged_data.responsibilities
    candidate.seniority_level = merged_data.seniority_level
    candidate.summary = merged_data.summary
    
    # Track Zoho metadata
    candidate.zoho_submission_id = zoho_submission_id
    candidate.zoho_form_id = zoho_form_id
    candidate.data_source_metadata = merged_data.data_sources
    candidate.last_zoho_sync = datetime.utcnow()
    
    logger.info(
        f"[MERGE] Candidate updated with merged data — "
        f"email={candidate.email} sources_tracked={len(merged_data.data_sources)}"
    )


def create_candidate_from_zoho_merge(
    db: Session,
    *,
    email: str,
    merged_data: "MergedCandidateData",
    raw_text: str,
    zoho_submission_id: str,
    zoho_form_id: str,
) -> Candidate:
    """
    Create a new Candidate from merged Zoho + extraction data.
    
    Args:
        db: Database session
        email: Candidate email (primary key)
        merged_data: Result from merge_sources()
        raw_text: Original resume text
        zoho_submission_id: Zoho submission ID
        zoho_form_id: Zoho form ID
    
    Returns:
        New Candidate instance (not yet committed)
    """
    candidate = Candidate(
        email=email,
        raw_text=raw_text,
        source_name="zoho_forms",
    )
    
    apply_merge_to_candidate(
        candidate,
        merged_data,
        zoho_submission_id,
        zoho_form_id,
    )
    
    db.add(candidate)
    
    log = ProcessingLog(
        entity_type="candidate",
        entity_id=email,
        status=ProcessingStatus.STRUCTURED,
    )
    db.add(log)
    
    logger.info(
        f"[MERGE] New candidate created from Zoho merge — "
        f"email={email} name={merged_data.name!r}"
    )
    
    return candidate
```

---

## Continued in Next Section...

This document continues with:
- **Week 2 (continued)**: API endpoint implementation
- **Week 3**: Schema updates and comprehensive testing
- **Week 4**: Deployment and monitoring

Due to length constraints, the full document should be split into separate files in production.

