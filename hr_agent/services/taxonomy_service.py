"""
Load and query the Mobavenue domain/subdomain taxonomy.

Used by domain classification validation and pool-building adjacency rules.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TAXONOMY_PATH = Path(__file__).parent.parent / "taxonomy" / "domains.json"


@lru_cache
def load_taxonomy() -> dict[str, Any]:
    data = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    logger.debug("[TAXONOMY] Loaded version %s — %d domains", data.get("version"), len(data.get("domains", [])))
    return data


def taxonomy_version() -> str:
    return load_taxonomy().get("version", "unknown")


def list_domains() -> list[dict[str, Any]]:
    """Return all domains with their subdomains (for API / UI)."""
    return load_taxonomy()["domains"]


def domain_codes() -> set[str]:
    return {d["code"] for d in list_domains()}


def subdomain_codes() -> set[str]:
    codes: set[str] = set()
    for domain in list_domains():
        for sub in domain.get("subdomains", []):
            codes.add(sub["code"])
    return codes


def get_domain(code: str) -> dict[str, Any] | None:
    for domain in list_domains():
        if domain["code"] == code:
            return domain
    return None


def get_subdomain(code: str) -> dict[str, Any] | None:
    for domain in list_domains():
        for sub in domain.get("subdomains", []):
            if sub["code"] == code:
                return {**sub, "domain_code": domain["code"], "domain_label": domain["label"]}
    return None


def subdomains_for_domain(domain_code: str) -> list[dict[str, Any]]:
    domain = get_domain(domain_code)
    if domain is None:
        return []
    return domain.get("subdomains", [])


def adjacent_subdomains(code: str) -> set[str]:
    sub = get_subdomain(code)
    if sub is None:
        return set()
    return set(sub.get("adjacent", []))


def validate_domain_code(code: str) -> bool:
    return code in domain_codes()


def validate_subdomain_codes(codes: list[str]) -> list[str]:
    """Return only codes that exist in the taxonomy."""
    valid = subdomain_codes()
    return [c for c in codes if c in valid]


def format_taxonomy_for_prompt() -> str:
    """Compact taxonomy listing for LLM classification prompts."""
    lines: list[str] = []
    for domain in list_domains():
        lines.append(f"DOMAIN {domain['code']}: {domain['label']} — {domain.get('description', '')}")
        for sub in domain.get("subdomains", []):
            lines.append(f"  SUBDOMAIN {sub['code']}: {sub['label']}")
    return "\n".join(lines)


def subdomain_domain_code(subdomain_code: str) -> str | None:
    sub = get_subdomain(subdomain_code)
    return sub["domain_code"] if sub else None
