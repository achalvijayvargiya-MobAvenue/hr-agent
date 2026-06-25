"""
LocalKBSource — serves candidates already stored in the local database.

This wraps the existing candidate table as a CandidateSource plugin so the
matching pipeline can pull from it via the standard source registry interface.
"""
import logging
from typing import Callable

from hr_agent.models.candidate import Candidate
from hr_agent.services.candidate_sources.base import CandidateRecord, CandidateSource

logger = logging.getLogger(__name__)


class LocalKBSource(CandidateSource):
    """
    Candidate source backed by the local PostgreSQL candidates table.
    Returns all fully-processed candidates (those with a normalized_role set).
    """

    def __init__(self, db_session_factory: Callable) -> None:
        self._session_factory = db_session_factory

    @property
    def name(self) -> str:
        return "local_kb"

    @property
    def display_name(self) -> str:
        return "Local Knowledge Base"

    def is_available(self) -> bool:
        return True

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        """
        Return all candidates whose CV has been fully extracted (normalized_role is set).
        The position_id is accepted for interface compatibility but not used for filtering
        here — broader filtering happens in the matching pipeline.
        """
        db = self._session_factory()
        try:
            candidates = (
                db.query(Candidate)
                .filter(Candidate.normalized_role.isnot(None))
                .all()
            )
            records = [
                CandidateRecord(
                    source_name="local_kb",
                    raw_text=candidate.raw_text or candidate.summary or "",
                    name=candidate.name,
                    location=candidate.location,
                    metadata={"candidate_email": candidate.email, "status": "existing"},
                )
                for candidate in candidates
            ]
            logger.debug(
                "LocalKBSource fetched %d candidate(s) for position_id=%s",
                len(records), position_id,
            )
            return records
        except Exception as exc:
            logger.error("LocalKBSource.fetch failed: %s", exc)
            return []
        finally:
            db.close()
