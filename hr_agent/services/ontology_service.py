"""
Ontology-based normalization for education, skills, tools, and certifications.

Resolves free-form strings (e.g. "L.L.B.", "Node") to canonical IDs so matching
is semantic rather than exact-string based.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

TAXONOMY_DIR = Path(__file__).parent.parent / "taxonomy"

OntologyKind = Literal["education", "skill", "cert"]


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@lru_cache
def _load_education() -> list[dict]:
    data = json.loads((TAXONOMY_DIR / "education.json").read_text(encoding="utf-8"))
    return data["entries"]


@lru_cache
def _load_skills() -> list[dict]:
    data = json.loads((TAXONOMY_DIR / "skills.json").read_text(encoding="utf-8"))
    return data["entries"]


def _build_alias_index(entries: list[dict]) -> dict[str, str]:
    """Map normalized alias -> canonical entry id."""
    index: dict[str, str] = {}
    for entry in entries:
        entry_id = entry["id"]
        for alias in entry.get("aliases", []) + [entry.get("label", "")]:
            norm = normalize_text(alias)
            if norm:
                index[norm] = entry_id
    return index


@lru_cache
def education_alias_index() -> dict[str, str]:
    return _build_alias_index(_load_education())


@lru_cache
def skill_alias_index() -> dict[str, str]:
    return _build_alias_index(_load_skills())


def resolve_education_ids(text: str) -> set[str]:
    """Return all canonical education IDs matched in `text`."""
    norm = normalize_text(text)
    if not norm:
        return set()

    matched: set[str] = set()
    index = education_alias_index()

    # Exact alias hit
    if norm in index:
        matched.add(index[norm])

    # Substring: alias contained in text or text contained in alias
    for alias, entry_id in index.items():
        if len(alias) >= 3 and (alias in norm or norm in alias):
            matched.add(entry_id)

    return matched


def resolve_skill_id(text: str) -> str | None:
    """Resolve a skill/tool/cert string to a canonical ID, or None."""
    norm = normalize_text(text)
    if not norm:
        return None

    index = skill_alias_index()
    if norm in index:
        return index[norm]

    # Substring match — prefer longest alias match to reduce false positives
    best: tuple[int, str] | None = None
    for alias, entry_id in index.items():
        if len(alias) < 3:
            continue
        if alias in norm or norm in alias:
            if best is None or len(alias) > best[0]:
                best = (len(alias), entry_id)
    return best[1] if best else None


def resolve_skill_ids_from_list(items: list[str]) -> set[str]:
    ids: set[str] = set()
    for item in items or []:
        sid = resolve_skill_id(item)
        if sid:
            ids.add(sid)
        else:
            # Fallback: treat normalized raw string as pseudo-id for exact fallback matching
            norm = normalize_text(item)
            if norm:
                ids.add(f"raw:{norm}")
    return ids


def education_entry_ids(education: list[dict] | None) -> set[str]:
    """Extract canonical education IDs from candidate education records."""
    ids: set[str] = set()
    for edu in education or []:
        if not isinstance(edu, dict):
            continue
        combined = f"{edu.get('degree') or ''} {edu.get('institution') or ''}"
        ids |= resolve_education_ids(combined)
    return ids


def education_requirement_satisfied(requirement: str, education: list[dict] | None) -> bool:
    """
    Check if a job education requirement is satisfied by candidate education.
    Uses ontology IDs first, then normalized substring fallback.
    """
    req_ids = resolve_education_ids(requirement)
    cand_ids = education_entry_ids(education)

    if req_ids and cand_ids and req_ids & cand_ids:
        return True

    # Fallback: normalized substring on combined degree+institution text
    req_norm = normalize_text(requirement)
    if not req_norm:
        return True

    for edu in education or []:
        if not isinstance(edu, dict):
            continue
        combined = normalize_text(f"{edu.get('degree') or ''} {edu.get('institution') or ''}")
        if req_norm in combined or combined in req_norm:
            return True
        # Word-level: all significant words from requirement appear
        req_words = {w for w in req_norm.split() if len(w) > 2}
        if req_words and req_words.issubset(set(combined.split())):
            return True

    return False


def skill_requirement_satisfied(requirement: str, candidate_items: list[str]) -> bool:
    """Check if a required skill/tool/cert is satisfied via ontology or raw match."""
    req_id = resolve_skill_id(requirement)
    cand_ids = resolve_skill_ids_from_list(candidate_items)

    if req_id and req_id in cand_ids:
        return True

    req_norm = normalize_text(requirement)
    if not req_norm:
        return True

    if f"raw:{req_norm}" in cand_ids:
        return True

    # Substring fallback on raw candidate strings
    for item in candidate_items or []:
        item_norm = normalize_text(item)
        if req_norm in item_norm or item_norm in req_norm:
            return True

    return False


def list_coverage_score(required: list[str], candidate_items: list[str]) -> float:
    """
    Fraction of required items satisfied by candidate pool using ontology matching.
    Returns 1.0 when required is empty.
    """
    if not required:
        return 1.0
    if not candidate_items:
        return 0.0

    satisfied = sum(1 for req in required if skill_requirement_satisfied(req, candidate_items))
    return round(satisfied / len(required), 4)


def get_entry_label(entry_id: str, kind: OntologyKind = "skill") -> str:
    entries = _load_education() if kind == "education" else _load_skills()
    for entry in entries:
        if entry["id"] == entry_id:
            return entry["label"]
    return entry_id
