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
