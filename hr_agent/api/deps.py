"""
FastAPI shared dependencies.

Service factory functions are zero-argument callables so FastAPI never
tries to interpret their signatures as route parameters.
The OpenAI client is cached at the module level (one instance per process).
"""
from functools import lru_cache

from openai import OpenAI

from hr_agent.config import get_settings
from hr_agent.core.permissions import get_current_user, require_role  # noqa: F401
from hr_agent.database import SessionLocal, get_db  # re-exported so routers import from one place
from hr_agent.services.candidate_sources.github import GitHubSource
from hr_agent.services.candidate_sources.local_kb import LocalKBSource
from hr_agent.services.candidate_sources.registry import SourceRegistry, source_registry
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services.extraction_service import ExtractionService
from hr_agent.services.matching_service import MatchingService
from hr_agent.services.pdf_service import extract_text as extract_pdf_text  # noqa: F401

__all__ = [
    "get_db",
    "get_settings",
    "get_openai_client",
    "get_extraction_service",
    "get_embedding_service",
    "get_matching_service",
    "get_source_registry",
    "extract_pdf_text",
    "get_current_user",
    "require_role",
]


@lru_cache
def get_openai_client() -> OpenAI:
    """Singleton OpenAI client — created once and reused across all requests."""
    return OpenAI(api_key=get_settings().openai_api_key)


def get_extraction_service() -> ExtractionService:
    """FastAPI dependency that returns an ExtractionService instance."""
    return ExtractionService(settings=get_settings(), client=get_openai_client())


def get_embedding_service() -> EmbeddingService:
    """FastAPI dependency that returns an EmbeddingService instance."""
    return EmbeddingService(settings=get_settings(), client=get_openai_client())


def get_matching_service() -> MatchingService:
    """FastAPI dependency that returns a MatchingService instance."""
    settings = get_settings()
    client = get_openai_client()
    embedding_svc = EmbeddingService(settings=settings, client=client)
    return MatchingService(settings=settings, client=client, embedding_service=embedding_svc)


@lru_cache
def get_source_registry() -> SourceRegistry:
    """
    Return the module-level source registry, with all built-in sources registered.
    The @lru_cache ensures registration only happens once per process.
    """
    local_kb = LocalKBSource(db_session_factory=SessionLocal)
    source_registry.register(local_kb)

    github = GitHubSource(db_session_factory=SessionLocal, settings=get_settings())
    source_registry.register(github)

    return source_registry
