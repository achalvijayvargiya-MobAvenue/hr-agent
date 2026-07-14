"""
Thin wrapper around the GitHub REST API for user search and profile enrichment.
"""
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT = 30


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns a non-success response."""


class GitHubClient:
    def __init__(self, token: str = "") -> None:
        self._session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._session.headers.update(headers)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{_API_BASE}{path}"
        response = self._session.request(method, url, timeout=_TIMEOUT, **kwargs)

        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            logger.debug("GitHub rate limit remaining: %s", remaining)

        if response.status_code == 403 and "rate limit" in response.text.lower():
            logger.error("GitHub API rate limit exceeded.")
            raise GitHubAPIError("GitHub API rate limit exceeded")

        if not response.ok:
            logger.error(
                "GitHub API %s %s failed: %s %s",
                method, path, response.status_code, response.text[:300],
            )
            raise GitHubAPIError(f"GitHub API error {response.status_code}")

        return response.json()

    def search_users(self, query: str, per_page: int = 30) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            "/search/users",
            params={"q": query, "per_page": per_page, "sort": "repositories", "order": "desc"},
        )
        return data.get("items", [])

    def get_user(self, login: str) -> dict[str, Any]:
        return self._request("GET", f"/users/{login}")

    def get_top_repos(self, login: str, per_page: int = 5) -> list[dict[str, Any]]:
        repos = self._request(
            "GET",
            f"/users/{login}/repos",
            params={"sort": "updated", "direction": "desc", "per_page": per_page},
        )
        return [r for r in repos if not r.get("fork")]
