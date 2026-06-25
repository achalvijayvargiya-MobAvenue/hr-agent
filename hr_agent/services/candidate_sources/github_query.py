"""
Build a GitHub user-search query from a Job record.

GitHub /search/users supports:
  - Free-text keywords  → matched against login, name, email
  - language:LANG       → users whose repos primarily use that language
  - location:PLACE      → profile location field
  - repos:>N            → minimum public repo count (experience proxy)
  - type:user           → personal accounts only (not orgs)

Queries must stay under 256 characters. Non-programming JD skills (e.g. "corporate
governance") are ignored — they do not map to GitHub search semantics.
"""
from dataclasses import dataclass, field

from hr_agent.models.job import Job

MAX_QUERY_LENGTH = 256

_GITHUB_LANGUAGES = {
    "python", "javascript", "typescript", "java", "go", "golang", "rust", "ruby",
    "php", "c", "c++", "cpp", "csharp", "c#", "swift", "kotlin", "scala", "shell",
    "bash", "r", "dart", "elixir", "haskell", "lua", "perl", "vue", "html", "css",
}

_LANG_ALIASES = {
    "golang": "go",
    "cpp": "c++",
    "c#": "csharp",
    "bash": "shell",
    "node.js": "javascript",
    "nodejs": "javascript",
}

# Frameworks/tools that are useful as free-text keywords (not language: qualifiers).
_DEV_KEYWORDS = {
    "fastapi", "django", "flask", "react", "vue", "angular", "nextjs", "next.js",
    "node", "express", "docker", "kubernetes", "k8s", "aws", "azure", "gcp",
    "postgresql", "postgres", "mongodb", "redis", "terraform", "graphql",
    "spring", "rails", "laravel", "dotnet", ".net", "machine learning", "ml",
    "devops", "backend", "frontend", "fullstack", "full-stack", "api",
}

_TECH_ROLE_HINTS = (
    "engineer", "developer", "devops", "architect", "programmer", "sre",
    "data scientist", "data engineer", "ml engineer", "software", "backend",
    "frontend", "fullstack", "full-stack", "security engineer", "platform",
)


@dataclass
class GitHubQueryPlan:
    """Human-readable breakdown of how a GitHub search query was constructed."""

    query: str | None
    suitable: bool
    reason: str
    role_keyword: str | None = None
    languages: list[str] = field(default_factory=list)
    dev_keywords: list[str] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)
    location: str | None = None
    repos_filter: str | None = None


def _normalize_language(skill: str) -> str | None:
    key = skill.strip().lower()
    if key in _LANG_ALIASES:
        key = _LANG_ALIASES[key]
    if key in _GITHUB_LANGUAGES:
        return key
    return None


def _normalize_dev_keyword(skill: str) -> str | None:
    key = skill.strip().lower()
    if key in _DEV_KEYWORDS:
        return key
    for hint in _DEV_KEYWORDS:
        if hint in key or key in hint:
            return key
    return None


def _quote_if_needed(value: str) -> str:
    if " " in value:
        return f'"{value}"'
    return value


def _role_keyword(job: Job) -> str | None:
    role = (job.normalized_role or job.title or "").replace("_", " ").strip()
    return role or None


def _repos_filter(job: Job) -> str | None:
    if job.experience_min is None:
        return None
    if job.experience_min >= 8:
        return "repos:>15"
    if job.experience_min >= 5:
        return "repos:>8"
    if job.experience_min >= 2:
        return "repos:>3"
    return None


def _collect_skills(job: Job) -> tuple[list[str], list[str], list[str]]:
    """Return (languages, dev_keywords, skipped_non_github_skills)."""
    languages: list[str] = []
    dev_keywords: list[str] = []
    skipped: list[str] = []
    seen_langs: set[str] = set()
    seen_kw: set[str] = set()

    for skill_list in (job.must_have_skills, job.good_to_have_skills, job.tools_and_technologies):
        if not skill_list:
            continue
        for skill in skill_list:
            if not isinstance(skill, str) or not skill.strip():
                continue
            lang = _normalize_language(skill)
            if lang and lang not in seen_langs:
                seen_langs.add(lang)
                languages.append(lang)
                continue
            dev_kw = _normalize_dev_keyword(skill)
            if dev_kw and dev_kw not in seen_kw:
                seen_kw.add(dev_kw)
                dev_keywords.append(dev_kw)
                continue
            skipped.append(skill.strip())

    return languages[:3], dev_keywords[:3], skipped


def _is_technical_role(job: Job, languages: list[str], dev_keywords: list[str]) -> bool:
    if languages or dev_keywords:
        return True
    role = _role_keyword(job)
    if not role:
        return False
    role_lower = role.lower()
    return any(hint in role_lower for hint in _TECH_ROLE_HINTS)


def _assemble_parts(
    role: str | None,
    languages: list[str],
    dev_keywords: list[str],
    location: str | None,
    repos_filter: str | None,
) -> list[str]:
    parts: list[str] = []
    if role:
        parts.append(role)
    for lang in languages:
        parts.append(f"language:{lang}")
    for kw in dev_keywords:
        parts.append(kw)
    if location:
        parts.append(f"location:{_quote_if_needed(location)}")
    if repos_filter:
        parts.append(repos_filter)
    parts.append("type:user")
    return parts


def _trim_to_limit(parts: list[str]) -> str:
    """Drop lowest-priority terms until the query fits GitHub's 256-char limit."""
    # Priority (drop first): dev keywords → role words → repos filter → location
    drop_order = []
    for i, part in enumerate(parts):
        if part == "type:user":
            continue
        if part.startswith("language:"):
            continue  # never drop languages first
        drop_order.append(i)

    # dev keywords and role are interleaved at start — rebuild with explicit priority
    working = list(parts)
    while len(" ".join(working)) > MAX_QUERY_LENGTH and len(working) > 1:
        removed = False
        for i in range(len(working) - 1, -1, -1):
            part = working[i]
            if part == "type:user" or part.startswith("language:"):
                continue
            working.pop(i)
            removed = True
            break
        if not removed:
            break
    return " ".join(working)


def plan_github_search(job: Job) -> GitHubQueryPlan:
    """
    Build a GitHubQueryPlan with query + explanation.
    Returns query=None when the position is not suitable for GitHub sourcing.
    """
    role = _role_keyword(job)
    languages, dev_keywords, skipped = _collect_skills(job)
    location = job.location
    repos_filter = _repos_filter(job)

    suitable = _is_technical_role(job, languages, dev_keywords)
    if not suitable:
        return GitHubQueryPlan(
            query=None,
            suitable=False,
            reason=(
                "Position has no programming languages, dev tools, or technical role title. "
                "GitHub search is for software/tech hiring only."
            ),
            role_keyword=role,
            languages=languages,
            dev_keywords=dev_keywords,
            skipped_skills=skipped[:8],
            location=location,
            repos_filter=repos_filter,
        )

    parts = _assemble_parts(role, languages, dev_keywords, location, repos_filter)
    query = _trim_to_limit(parts)

    return GitHubQueryPlan(
        query=query,
        suitable=True,
        reason="Technical signals found in JD — query built for GitHub user search.",
        role_keyword=role,
        languages=languages,
        dev_keywords=dev_keywords,
        skipped_skills=skipped[:8],
        location=location,
        repos_filter=repos_filter,
    )


def build_github_search_query(job: Job) -> str | None:
    """Return the GitHub search query string, or None if the job is not suitable."""
    return plan_github_search(job).query
