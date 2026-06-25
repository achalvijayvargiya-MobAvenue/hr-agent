"""
GitHubSource — discovers developer candidates via the GitHub REST API.

Loads the position (Job) from the database, builds a search query from its
extracted fields, and returns normalised CandidateRecords for the matching pipeline.
"""
import json
import logging
import os
from typing import Any, Callable

from hr_agent.config import Settings
from hr_agent.models.candidate import Candidate
from hr_agent.models.job import Job
from hr_agent.services.candidate_service import normalize_email
from hr_agent.services.candidate_sources.base import CandidateRecord, CandidateSource
from hr_agent.services.candidate_sources.github_client import GitHubAPIError, GitHubClient
from hr_agent.services.candidate_sources.github_query import GitHubQueryPlan, plan_github_search

logger = logging.getLogger(__name__)

_DEMO_DATA_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "github_demo_profiles.json")
)


def _profile_to_raw_text(user: dict[str, Any], repos: list[dict[str, Any]] | None = None) -> str:
    """Convert a GitHub user (+ optional repos) into CV-like text for LLM extraction."""
    login = user.get("login", "")
    lines: list[str] = [
        f"Name: {user.get('name') or login}",
        f"GitHub: https://github.com/{login}",
    ]

    if user.get("company"):
        lines.append(f"Company: {user['company']}")
    if user.get("location"):
        lines.append(f"Location: {user['location']}")
    if user.get("email"):
        lines.append(f"Email: {user['email']}")
    if user.get("blog"):
        lines.append(f"Website: {user['blog']}")
    if user.get("bio"):
        lines.append(f"\nBio:\n{user['bio']}")

    lines.append(
        f"\nGitHub stats: {user.get('public_repos', 0)} public repos, "
        f"{user.get('followers', 0)} followers"
    )
    if user.get("hireable") is True:
        lines.append("Open to opportunities: yes")

    if repos:
        lines.append("\nTop repositories:")
        for repo in repos:
            lang = repo.get("language") or "unknown"
            stars = repo.get("stargazers_count", 0)
            desc = (repo.get("description") or "").strip()
            lines.append(f"- {repo.get('name')} ({lang}): {desc} ★{stars}")

    return "\n".join(lines)


class GitHubSource(CandidateSource):
    """Candidate source backed by the public GitHub REST API."""

    def __init__(
        self,
        db_session_factory: Callable,
        settings: Settings,
    ) -> None:
        self._session_factory = db_session_factory
        self._settings = settings
        self._client = GitHubClient(token=settings.github_token)

    @property
    def name(self) -> str:
        return "github"

    @property
    def display_name(self) -> str:
        return "GitHub"

    def is_available(self) -> bool:
        return bool(self._settings.github_token) or self._settings.github_demo_mode

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        db = self._session_factory()
        try:
            job = db.query(Job).filter_by(id=position_id).first()
            if job is None:
                logger.warning("GitHubSource: position %s not found.", position_id)
                return []

            query_plan = plan_github_search(job)
            self._log_query_plan(position_id, query_plan)

            if self._settings.github_demo_mode:
                return self._fetch_demo(position_id, query_plan, db)

            if not query_plan.suitable or not query_plan.query:
                return []

            if not self._settings.github_token:
                logger.warning("GitHubSource: GITHUB_TOKEN not set — cannot call GitHub API.")
                return []

            try:
                search_results = self._client.search_users(
                    query_plan.query, per_page=self._settings.github_max_results,
                )
            except GitHubAPIError as exc:
                logger.error("GitHubSource search failed: %s", exc)
                return []

            if not search_results:
                logger.info("GitHubSource: no users matched for position_id=%s", position_id)
                return []

            return self._build_records(
                search_results, query_plan.query, position_id, db,
            )

        except Exception as exc:
            logger.error("GitHubSource.fetch failed for position %s: %s", position_id, exc)
            return []
        finally:
            db.close()

    def _log_query_plan(self, position_id: str, plan: GitHubQueryPlan) -> None:
        logger.info(
            "GitHubSource: query plan for position_id=%s — suitable=%s  query=%r  "
            "role=%r  languages=%s  dev_keywords=%s  location=%r  repos=%s  "
            "skipped_skills=%s  reason=%s",
            position_id,
            plan.suitable,
            plan.query,
            plan.role_keyword,
            plan.languages,
            plan.dev_keywords,
            plan.location,
            plan.repos_filter,
            plan.skipped_skills,
            plan.reason,
        )

    def _fetch_demo(
        self, position_id: str, plan: GitHubQueryPlan, db,
    ) -> list[CandidateRecord]:
        """Return sample profiles from data/github_demo_profiles.json (no API call)."""
        if not os.path.isfile(_DEMO_DATA_FILE):
            logger.warning("GitHubSource demo mode: file not found at %r", _DEMO_DATA_FILE)
            return []

        with open(_DEMO_DATA_FILE, encoding="utf-8") as fh:
            profiles = json.load(fh)

        logger.info(
            "GitHubSource: DEMO MODE — returning %d sample profile(s) for position_id=%s "
            "(query would have been: %r)",
            len(profiles), position_id, plan.query,
        )

        seen_logins = self._existing_github_logins(db)
        records: list[CandidateRecord] = []
        for profile in profiles:
            login = profile.get("login")
            if not login or login in seen_logins:
                continue
            raw_text = _profile_to_raw_text(profile, profile.get("repos"))
            records.append(
                CandidateRecord(
                    source_name="github",
                    raw_text=raw_text,
                    source_url=profile.get("html_url") or f"https://github.com/{login}",
                    name=profile.get("name") or login,
                    email=normalize_email(profile.get("email")),
                    location=profile.get("location"),
                    metadata={
                        "github_login": login,
                        "search_query": plan.query,
                        "position_id": position_id,
                        "demo": True,
                    },
                )
            )
            seen_logins.add(login)
        return records

    def _build_records(
        self,
        search_results: list[dict[str, Any]],
        query: str,
        position_id: str,
        db,
    ) -> list[CandidateRecord]:
        seen_logins = self._existing_github_logins(db)
        records: list[CandidateRecord] = []

        for item in search_results:
            login = item.get("login")
            if not login or login in seen_logins:
                continue

            user = self._enrich_user(login, item)
            repos = self._fetch_repos(login) if self._settings.github_enrich_profiles else None
            raw_text = _profile_to_raw_text(user, repos)

            records.append(
                CandidateRecord(
                    source_name="github",
                    raw_text=raw_text,
                    source_url=user.get("html_url") or f"https://github.com/{login}",
                    name=user.get("name") or login,
                    email=normalize_email(user.get("email")),
                    location=user.get("location"),
                    metadata={
                        "github_login": login,
                        "search_query": query,
                        "position_id": position_id,
                    },
                )
            )
            seen_logins.add(login)

        logger.info(
            "GitHubSource fetched %d new profile(s) for position_id=%s",
            len(records), position_id,
        )
        return records

    def _existing_github_logins(self, db) -> set[str]:
        """Return GitHub logins already stored as candidates (avoid duplicate imports)."""
        candidates = db.query(Candidate).filter(Candidate.source_name == "github").all()
        logins: set[str] = set()
        for candidate in candidates:
            if candidate.raw_text:
                for line in candidate.raw_text.splitlines():
                    if "github.com/" in line.lower():
                        login = line.rstrip("/").split("/")[-1].strip()
                        if login:
                            logins.add(login)
                        break
        return logins

    def _enrich_user(self, login: str, search_item: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.github_enrich_profiles:
            return search_item
        try:
            return self._client.get_user(login)
        except GitHubAPIError:
            logger.warning("GitHubSource: could not enrich user %r, using search result.", login)
            return search_item

    def _fetch_repos(self, login: str) -> list[dict[str, Any]]:
        try:
            return self._client.get_top_repos(login, per_page=5)
        except GitHubAPIError:
            logger.warning("GitHubSource: could not fetch repos for %r.", login)
            return []
