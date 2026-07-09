import logging
from typing import Any
import requests

from hr_agent.config import get_settings
from hr_agent.services.zoho.auth import ZohoAuthManager

logger = logging.getLogger(__name__)

class ZohoRecruitClient:
    def __init__(self):
        self.settings = get_settings()
        self.auth_manager = ZohoAuthManager()
        # Zoho Recruit API base URL (V2)
        # We extract the TLD from accounts.zoho.in -> zoho.in
        tld = self.settings.zoho_dc.split(".")[-1]
        self.base_url = f"https://recruit.zoho.{tld}/recruit/v2"

    def _get_headers(self) -> dict[str, str]:
        token = self.auth_manager.get_valid_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}"
        }

    def get_active_jobs(self) -> list[dict[str, Any]]:
        """Fetch all active job openings from Zoho."""
        url = f"{self.base_url}/Job_Openings"
        headers = self._get_headers()
        
        logger.info(f"Fetching Job Openings from Zoho: {url}")
        response = requests.get(url, headers=headers)
        if response.status_code == 204:
            return []
        if response.status_code != 200:
            logger.error(f"Failed to fetch jobs: {response.text}")
            return []
            
        data = response.json()
        return data.get("data", [])

    def get_applications_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Fetch all applications linked to a specific job opening."""
        url = f"{self.base_url}/Applications/search"
        params = {
            "criteria": f"(Job_Opening_ID:equals:{job_id})"
        }
        headers = self._get_headers()
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 204:
            return []
        elif response.status_code != 200:
            logger.error(f"Failed to fetch applications for job {job_id}: {response.text}")
            return []
            
        data = response.json()
        return data.get("data", [])

    def get_candidate_details(self, candidate_id: str) -> dict[str, Any] | None:
        """Fetch specific candidate details."""
        url = f"{self.base_url}/Candidates/{candidate_id}"
        headers = self._get_headers()
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch candidate {candidate_id}: {response.text}")
            return None
            
        data = response.json()
        items = data.get("data", [])
        return items[0] if items else None

    def get_candidate_attachments(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get the list of attachments (CVs) for a candidate."""
        url = f"{self.base_url}/Candidates/{candidate_id}/Attachments"
        headers = self._get_headers()
        
        response = requests.get(url, headers=headers)
        if response.status_code == 204:
            return []
        elif response.status_code != 200:
            logger.error(f"Failed to fetch attachments metadata for candidate {candidate_id}: {response.text}")
            return []
            
        data = response.json()
        return data.get("data", [])
        
    def download_attachment(self, candidate_id: str, attachment_id: str) -> bytes | None:
        """Download the actual binary content of an attachment."""
        url = f"{self.base_url}/Candidates/{candidate_id}/Attachments/{attachment_id}"
        headers = self._get_headers()
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to download attachment {attachment_id} for candidate {candidate_id}")
            return None
            
        return response.content
