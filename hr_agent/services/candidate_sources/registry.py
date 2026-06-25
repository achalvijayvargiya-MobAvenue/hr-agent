"""
Source registry — holds and dispatches to all registered CandidateSource instances.
"""
import logging

from hr_agent.services.candidate_sources.base import CandidateRecord, CandidateSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """
    Holds all registered CandidateSource instances.
    Sources self-register by calling registry.register(source_instance).
    """

    def __init__(self) -> None:
        self._sources: dict[str, CandidateSource] = {}

    def register(self, source: CandidateSource) -> None:
        """Register a source under its name. Overwrites any existing entry with the same name."""
        self._sources[source.name] = source
        logger.debug("Registered candidate source: %r", source.name)

    def get(self, name: str) -> CandidateSource | None:
        """Return the source with the given name, or None if not registered."""
        return self._sources.get(name)

    def list_available(self) -> list[CandidateSource]:
        """Return only sources where is_available() is True."""
        return [s for s in self._sources.values() if s.is_available()]

    def fetch_all(
        self,
        position_id: str,
        source_names: list[str] | None = None,
    ) -> list[CandidateRecord]:
        """
        Fetch candidates from all available sources (or a named subset).
        Aggregates results into a single flat list.
        """
        sources = (
            [self._sources[n] for n in source_names if n in self._sources]
            if source_names is not None
            else self.list_available()
        )

        results: list[CandidateRecord] = []
        for source in sources:
            try:
                records = source.fetch(position_id)
                logger.debug(
                    "Source %r returned %d record(s) for position %s",
                    source.name, len(records), position_id,
                )
                results.extend(records)
            except Exception as exc:
                logger.error(
                    "Source %r raised an unexpected error for position %s: %s",
                    source.name, position_id, exc,
                )
        return results


# Module-level singleton used throughout the application
source_registry = SourceRegistry()
