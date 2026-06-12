"""
Import all models here so SQLAlchemy's metadata is populated before
`Base.metadata.create_all()` or Alembic autogenerate runs.
"""
from hr_agent.models.candidate import Candidate
from hr_agent.models.embedding import Embedding
from hr_agent.models.job import Job
from hr_agent.models.match_result import MatchResult
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus

__all__ = [
    "Job",
    "Candidate",
    "Embedding",
    "MatchResult",
    "ProcessingLog",
    "ProcessingStatus",
]
