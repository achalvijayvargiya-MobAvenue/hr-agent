"""
ZohoSource — candidate source backed by Zoho Recruit.

Phase 1: registration + availability only.
Later phases add sync-backed fetch() for position-mapped applications.
"""
import logging
from typing import Callable

from hr_agent.config import Settings
from hr_agent.services.candidate_sources.base import CandidateRecord, CandidateSource
from hr_agent.services.candidate_sources.zoho.auth import ZohoAuthManager
from hr_agent.services.candidate_sources.zoho.client import ZohoClient

logger = logging.getLogger(__name__)


class ZohoSource(CandidateSource):
    def __init__(
        self,
        db_session_factory: Callable,
        settings: Settings,
        client: ZohoClient | None = None,
    ) -> None:
        self._session_factory = db_session_factory
        self._settings = settings
        auth = ZohoAuthManager(settings)
        self._client = client or ZohoClient(settings, auth)

    @property
    def name(self) -> str:
        return "zoho"

    @property
    def display_name(self) -> str:
        return "Zoho Recruit"

    def is_available(self) -> bool:
        return self._settings.zoho_demo_mode or self._client.auth.is_configured()

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        """Return Zoho candidates linked to the mapped job opening for this position."""
        from hr_agent.services.candidate_sources.zoho.source_fetch import fetch_for_position

        db = self._session_factory()
        try:
            return fetch_for_position(db, self._settings, position_id)
        except Exception as exc:
            logger.error("ZohoSource.fetch failed for position %s: %s", position_id, exc)
            return []
        finally:
            db.close()

    @property
    def client(self) -> ZohoClient:
        return self._client
