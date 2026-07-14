import logging
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from hr_agent.core.config import get_settings
from hr_agent.modules.integrations.zoho.auth import ZohoAuthManager
from hr_agent.core.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

class ZohoRecruitClient:
    def __init__(self):
        self.settings = get_settings()
        self.auth_manager = ZohoAuthManager()
        # We extract the TLD from accounts.zoho.in -> zoho.in
        tld = self.settings.zoho_dc.split(".")[-1]
        self.base_url = f"https://recruit.zoho.{tld}/recruit/v2"
        self.session = self._create_retry_session()

    def _create_retry_session(self) -> requests.Session:
        session = requests.Session()
        # Retry on standard rate limits (429) and server errors (500, 502, 503, 504)
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_headers(self) -> dict[str, str]:
        token = self.auth_manager.get_valid_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}"
        }

    @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    def get_active_jobs(self) -> list[dict[str, Any]]:
        """Fetch all active job openings from Zoho."""
        url = f"{self.base_url}/Job_Openings"
        headers = self._get_headers()
        
        logger.info(f"Fetching Job Openings from Zoho: {url}")
        try:
            response = self.session.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed after retries: {e}")
            return []
            
        if response.status_code == 204:
            return []
        if response.status_code != 200:
            logger.error(f"Failed to fetch jobs: {response.text}")
            return []
            
        data = response.json()
        return data.get("data", [])

    @circuit_breaker(failure_threshold=3, recovery_timeout=60)
    def get_applications_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Fetch all applications linked to a specific job opening."""
        # Step 1: Get the Job_Opening_ID string (e.g. ZR_39_JOB) from the numeric job_id
        job_url = f"{self.base_url}/Job_Openings/{job_id}"
        headers = self._get_headers()
        try:
            job_res = self.session.get(job_url, headers=headers)
            if job_res.status_code == 200:
                job_data = job_res.json().get("data", [])
                if job_data:
                    zr_id = job_data[0].get("Job_Opening_ID")
                    if zr_id:
                        # Step 2: Search applications by the ZR_ID
                        url = f"{self.base_url}/Applications/search"
                        params = {
                            "criteria": f"(Job_Opening_ID:equals:{zr_id})"
                        }
                        try:
                            response = self.session.get(url, headers=headers, params=params)
                            if response.status_code == 200:
                                return response.json().get("data", [])
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Request failed for applications search: {e}")
                            
        except Exception as e:
            logger.error(f"Failed to fetch job {job_id} to resolve ZR_ID: {e}")
            
        return []

    def get_candidate_details(self, candidate_id: str) -> dict[str, Any] | None:
        """Fetch specific candidate details."""
        url = f"{self.base_url}/Candidates/{candidate_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed after retries for candidate {candidate_id}: {e}")
            return None
            
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
        
        try:
            response = self.session.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed after retries for attachments metadata for candidate {candidate_id}: {e}")
            return []
            
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
        
        try:
            response = self.session.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed after retries for attachment {attachment_id} for candidate {candidate_id}: {e}")
            return None
            
        if response.status_code != 200:
            logger.error(f"Failed to download attachment {attachment_id} for candidate {candidate_id}")
            return None
            
        return response.content
