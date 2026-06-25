"""
Base abstractions for the candidate-source plugin system.

CandidateRecord  — normalised data returned by every source
CandidateSource  — ABC that all concrete sources must implement
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CandidateRecord:
    """Normalised candidate data returned by any source."""

    source_name: str
    raw_text: str               # full text content of the CV/profile
    source_url: str | None = None
    metadata: dict = field(default_factory=dict)
    # Optional pre-filled fields (sources that return structured data can set these)
    name: str | None = None
    email: str | None = None
    location: str | None = None


class CandidateSource(ABC):
    """
    Abstract base for all candidate sources.
    Each concrete source must implement fetch() and the name property.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique machine-readable source identifier, e.g. 'local_kb'."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable label shown in the UI."""
        return self.name

    @abstractmethod
    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        """
        Fetch candidates relevant to the given position.
        Must return a list of CandidateRecord — empty list if none found.
        Should NOT raise exceptions; log and return [] on failure.
        """
        ...

    def is_available(self) -> bool:
        """Return False if the source is misconfigured or unavailable."""
        return True
