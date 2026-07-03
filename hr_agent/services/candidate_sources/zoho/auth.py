"""
Zoho OAuth 2.0 token management.

Uses a long-lived refresh token (stored in env) to obtain short-lived access tokens.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import requests

from hr_agent.config import Settings

logger = logging.getLogger(__name__)

_TOKEN_SKEW_SECONDS = 60


class ZohoAuthError(Exception):
    """Raised when OAuth token refresh fails."""


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float


class ZohoAuthManager:
    """Thread-safe in-memory OAuth token cache with proactive refresh."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: _TokenCache | None = None
        self._lock = threading.Lock()
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def is_configured(self) -> bool:
        if self._settings.zoho_demo_mode:
            return True
        return bool(
            self._settings.zoho_client_id
            and self._settings.zoho_client_secret
            and self._settings.zoho_refresh_token
        )

    def get_access_token(self) -> str:
        if self._settings.zoho_demo_mode:
            return "demo-token"

        if not self.is_configured():
            raise ZohoAuthError(
                "Zoho OAuth is not configured — set ZOHO_CLIENT_ID, "
                "ZOHO_CLIENT_SECRET, and ZOHO_REFRESH_TOKEN."
            )

        with self._lock:
            if self._cache and time.time() < self._cache.expires_at:
                return self._cache.access_token
            return self._refresh_locked()

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    def _refresh_locked(self) -> str:
        url = f"{self._settings.zoho_accounts_url.rstrip('/')}/oauth/v2/token"
        payload = {
            "refresh_token": self._settings.zoho_refresh_token,
            "client_id": self._settings.zoho_client_id,
            "client_secret": self._settings.zoho_client_secret,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
        except requests.RequestException as exc:
            self._last_error = str(exc)
            raise ZohoAuthError(f"OAuth token request failed: {exc}") from exc

        if not response.ok:
            self._last_error = response.text[:500]
            logger.error("[ZOHO:AUTH] Token refresh failed: %s %s", response.status_code, self._last_error)
            raise ZohoAuthError(f"OAuth token refresh failed ({response.status_code})")

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            self._last_error = "Response missing access_token"
            raise ZohoAuthError("OAuth response missing access_token")

        expires_in = int(data.get("expires_in", 3600))
        self._cache = _TokenCache(
            access_token=access_token,
            expires_at=time.time() + max(expires_in - _TOKEN_SKEW_SECONDS, 30),
        )
        self._last_error = None
        logger.info("[ZOHO:AUTH] Access token refreshed — expires_in=%ss", expires_in)
        return access_token
