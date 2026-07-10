from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hr_agent.config import Settings


class ZohoTokenStoreBase:
    def save(
        self,
        *,
        refresh_token: str | None = None,
        access_token: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        raise NotImplementedError

    def load(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_refresh_token(self) -> str | None:
        return self.load().get("refresh_token")

    def get_access_token(self) -> str | None:
        return self.load().get("access_token")

    def get_expires_at(self) -> float | None:
        return self.load().get("expires_at")


class ZohoTokenFileStore(ZohoTokenStoreBase):
    """Simple local token store for Zoho OAuth in development.

    Stores refresh_token and cached access_token data in a JSON file.
    """

    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.zoho_token_store_path)

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                return json.load(fh) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(
        self,
        *,
        refresh_token: str | None = None,
        access_token: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        data = self.load()
        if refresh_token is not None:
            data["refresh_token"] = refresh_token
        if access_token is not None:
            data["access_token"] = access_token
        if expires_at is not None:
            data["expires_at"] = expires_at

        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
        temp_path.replace(self._path)


class ZohoTokenDBStore(ZohoTokenStoreBase):
    """Database-backed token storage for production deployments."""

    def __init__(self, settings: Settings) -> None:
        from hr_agent.database import SessionLocal
        from hr_agent.models.zoho_oauth_token import ZohoOAuthToken

        self._session_factory = SessionLocal
        self._service_name = settings.zoho_token_service_name
        self._model = ZohoOAuthToken

    def load(self) -> dict[str, Any]:
        session = self._session_factory()
        try:
            token_row = session.query(self._model).filter_by(service_name=self._service_name).first()
            if token_row is None:
                return {}
            return {
                "refresh_token": token_row.refresh_token,
                "access_token": token_row.access_token,
                "expires_at": token_row.expires_at,
            }
        finally:
            session.close()

    def save(
        self,
        *,
        refresh_token: str | None = None,
        access_token: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        session = self._session_factory()
        try:
            token_row = session.query(self._model).filter_by(service_name=self._service_name).first()
            if token_row is None:
                token_row = self._model(service_name=self._service_name)
                session.add(token_row)
            if refresh_token is not None:
                token_row.refresh_token = refresh_token
            if access_token is not None:
                token_row.access_token = access_token
            if expires_at is not None:
                token_row.expires_at = expires_at
            session.commit()
        finally:
            session.close()


class ZohoTokenStore:
    """Factory wrapper that picks the configured storage backend."""

    def __new__(cls, settings: Settings) -> ZohoTokenStoreBase:
        if settings.zoho_token_storage.lower() == "db":
            return ZohoTokenDBStore(settings)
        return ZohoTokenFileStore(settings)
