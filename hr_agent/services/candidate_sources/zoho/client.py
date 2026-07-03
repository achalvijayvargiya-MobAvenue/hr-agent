"""
HTTP client for the Zoho Recruit v2 REST API.

Mirrors the GitHub client pattern: session, structured errors, retry with backoff.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from hr_agent.config import Settings
from hr_agent.services.candidate_sources.zoho.auth import ZohoAuthError, ZohoAuthManager

logger = logging.getLogger(__name__)

_TIMEOUT = 30
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0


class ZohoAPIError(Exception):
    """Raised when the Zoho Recruit API returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ZohoClient:
    def __init__(self, settings: Settings, auth: ZohoAuthManager | None = None) -> None:
        self._settings = settings
        self._auth = auth or ZohoAuthManager(settings)
        self._session = requests.Session()

    @property
    def auth(self) -> ZohoAuthManager:
        return self._auth

    def health_check(self) -> dict[str, Any]:
        """Verify OAuth and API connectivity."""
        if self._settings.zoho_demo_mode:
            return {
                "ok": True,
                "demo_mode": True,
                "message": "Zoho demo mode — no live API calls.",
            }

        if not self._auth.is_configured():
            return {
                "ok": False,
                "demo_mode": False,
                "message": "Zoho OAuth credentials are not configured.",
            }

        try:
            self._auth.get_access_token()
            self.list_candidates(page=1, per_page=1)
            return {"ok": True, "demo_mode": False, "message": "OAuth and API reachable."}
        except (ZohoAuthError, ZohoAPIError) as exc:
            return {"ok": False, "demo_mode": False, "message": str(exc)}

    def list_candidates(
        self,
        *,
        page: int = 1,
        per_page: int = 200,
        modified_since: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "sort_by": "Modified_Time",
            "sort_order": "desc",
        }
        if modified_since:
            params["criteria"] = f"(Modified_Time:greater_than:{modified_since})"
        return self._request_json("GET", "/Candidates", params=params)

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/Candidates/{candidate_id}")

    def list_attachments(self, candidate_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/Candidates/{candidate_id}/Attachments")

    def download_attachment(self, candidate_id: str, attachment_id: str) -> bytes:
        return self._request_bytes("GET", f"/Candidates/{candidate_id}/Attachments/{attachment_id}")

    def list_job_openings(
        self,
        *,
        page: int = 1,
        per_page: int = 200,
        modified_since: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "sort_by": "Modified_Time",
            "sort_order": "desc",
        }
        if modified_since:
            params["criteria"] = f"(Modified_Time:greater_than:{modified_since})"
        return self._request_json("GET", "/Job_Openings", params=params)

    def list_applications(
        self,
        *,
        page: int = 1,
        per_page: int = 200,
        modified_since: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "sort_by": "Modified_Time",
            "sort_order": "desc",
        }
        if modified_since:
            params["criteria"] = f"(Modified_Time:greater_than:{modified_since})"
        return self._request_json("GET", "/Applications", params=params)

    def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request(method, path, **kwargs)
        if not response.content:
            return {}
        return response.json()

    def _request_bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        response = self._request(method, path, **kwargs)
        return response.content

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if self._settings.zoho_demo_mode:
            raise ZohoAPIError("Live API calls are disabled in Zoho demo mode")

        url = f"{self._settings.zoho_recruit_api_url.rstrip('/')}{path}"
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                token = self._auth.get_access_token()
                headers = kwargs.pop("headers", {})
                headers["Authorization"] = f"Zoho-oauthtoken {token}"
                response = self._session.request(
                    method, url, timeout=_TIMEOUT, headers=headers, **kwargs
                )
            except requests.RequestException as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 401 and attempt < _MAX_RETRIES - 1:
                logger.warning("[ZOHO:API] 401 on %s — invalidating token and retrying.", path)
                self._auth.invalidate()
                self._sleep_backoff(attempt)
                continue

            if response.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    time.sleep(float(retry_after))
                else:
                    self._sleep_backoff(attempt)
                continue

            if not response.ok:
                logger.error(
                    "[ZOHO:API] %s %s failed: %s %s",
                    method, path, response.status_code, response.text[:300],
                )
                raise ZohoAPIError(
                    f"Zoho API error {response.status_code} on {path}",
                    status_code=response.status_code,
                )

            return response

        if last_exc:
            raise ZohoAPIError(f"Zoho API network error on {path}: {last_exc}") from last_exc
        raise ZohoAPIError(f"Zoho API request failed on {path} after retries")

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(_BACKOFF_BASE ** attempt)
