"""
LinkedInSource — reads candidates from a local JSON file.

This is a stub that demonstrates the plugin pattern without hitting the real
LinkedIn API. Swap the file with real API data (or a live integration) later
without changing any other code.
"""
import json
import logging
import os

from hr_agent.services.candidate_sources.base import CandidateRecord, CandidateSource

logger = logging.getLogger(__name__)

_DEFAULT_DATA_FILE = os.path.join(
    os.path.dirname(__file__),   # .../hr_agent/services/candidate_sources/
    "..", "..", "..",             # up to project root
    "data", "linkedin_candidates.json",
)


class LinkedInSource(CandidateSource):
    """
    Candidate source backed by a local JSON file of LinkedIn-style profiles.

    Expected JSON format (list of objects):
        [{"name": str, "location": str, "summary": str, "url": str (optional)}, ...]
    """

    def __init__(self, data_file: str | None = None) -> None:
        self._data_file = os.path.normpath(
            data_file if data_file is not None else _DEFAULT_DATA_FILE
        )

    @property
    def name(self) -> str:
        return "linkedin"

    @property
    def display_name(self) -> str:
        return "LinkedIn"

    def is_available(self) -> bool:
        return os.path.isfile(self._data_file)

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        if not os.path.isfile(self._data_file):
            logger.warning(
                "LinkedInSource: data file not found at %r — returning empty list.",
                self._data_file,
            )
            return []

        try:
            with open(self._data_file, encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception as exc:
            logger.error("LinkedInSource: failed to load %r: %s", self._data_file, exc)
            return []

        records: list[CandidateRecord] = []
        for entry in raw:
            records.append(
                CandidateRecord(
                    source_name="linkedin",
                    raw_text=entry.get("summary", ""),
                    source_url=entry.get("url"),
                    name=entry.get("name"),
                    email=entry.get("email"),
                    location=entry.get("location"),
                    metadata={"source_file": self._data_file},
                )
            )

        logger.debug(
            "LinkedInSource fetched %d record(s) for position_id=%s",
            len(records), position_id,
        )
        return records
