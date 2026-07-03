"""
Import all models here so SQLAlchemy's metadata is populated before
`Base.metadata.create_all()` or Alembic autogenerate runs.
"""
from hr_agent.models.candidate import Candidate
from hr_agent.models.candidate_import import CandidateImport, ImportStatus
from hr_agent.models.embedding import Embedding
from hr_agent.models.job import Job
from hr_agent.models.job_candidate_pool import JobCandidatePool
from hr_agent.models.match_result import MatchResult
from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
from hr_agent.models.sync_metadata import SyncMetadata
from hr_agent.models.user import User
from hr_agent.models.role import Role
from hr_agent.models.user_role import UserRole
from hr_agent.models.zoho_application import ZohoApplication
from hr_agent.models.zoho_candidate import ZohoCandidate
from hr_agent.models.zoho_job_opening import ZohoJobOpening

__all__ = [
    "Job",
    "JobCandidatePool",
    "Candidate",
    "CandidateImport",
    "ImportStatus",
    "Embedding",
    "MatchResult",
    "ProcessingLog",
    "ProcessingStatus",
    "SyncMetadata",
    "ZohoCandidate",
    "ZohoJobOpening",
    "ZohoApplication",
    "User",
    "Role",
    "UserRole",
]
