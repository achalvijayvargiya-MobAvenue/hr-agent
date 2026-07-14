"""
LLM-based domain/subdomain classification constrained to the Mobavenue taxonomy.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from hr_agent.core.config import Settings
from hr_agent.modules.taxonomy.schemas import DomainClassification
import hr_agent.modules.taxonomy.taxonomy_service as taxonomy_service

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class DomainClassificationError(Exception):
    """Raised when classification fails after retries."""


class DomainClassificationService:
    def __init__(self, settings: Settings, client: OpenAI) -> None:
        self._settings = settings
        self._client = client
        self._prompt_template = (PROMPTS_DIR / "domain_classification.txt").read_text(encoding="utf-8")

    def classify_job(
        self,
        *,
        title: str | None,
        normalized_role: str | None,
        seniority_level: str | None = None,
        department: str | None = None,
        industry: str | None = None,
        skills: list[str] | None = None,
        tools: list[str] | None = None,
        responsibilities: list[str] | None = None,
        education: list[str] | None = None,
        summary: str | None = None,
    ) -> DomainClassification:
        return self._classify(
            entity_type="JOB",
            title_or_role=title or "",
            normalized_role=normalized_role or "",
            seniority_level=seniority_level,
            department=department,
            industry=industry,
            skills=skills,
            tools=tools,
            responsibilities=responsibilities,
            experience_areas=None,
            education=education,
            summary=summary,
        )

    def classify_candidate(
        self,
        *,
        current_title: str | None,
        normalized_role: str | None,
        seniority_level: str | None = None,
        industries: list[str] | None = None,
        skills: list[str] | None = None,
        tools: list[str] | None = None,
        responsibilities: list[str] | None = None,
        experience_areas: list[str] | None = None,
        education: list | None = None,
        summary: str | None = None,
    ) -> DomainClassification:
        edu_text = "; ".join(
            f"{e.get('degree', '')} {e.get('institution', '')}".strip()
            for e in (education or [])
            if isinstance(e, dict)
        )
        return self._classify(
            entity_type="CANDIDATE",
            title_or_role=current_title or "",
            normalized_role=normalized_role or "",
            seniority_level=seniority_level,
            department=None,
            industry=", ".join(industries) if industries else None,
            skills=skills,
            tools=tools,
            responsibilities=responsibilities,
            experience_areas=experience_areas,
            education=edu_text or None,
            summary=summary,
        )

    def _classify(self, **fields: object) -> DomainClassification:
        prompt = self._prompt_template.format(
            taxonomy_block=taxonomy_service.format_taxonomy_for_prompt(),
            entity_type=fields.get("entity_type", "PROFILE"),
            title_or_role=fields.get("title_or_role") or "not specified",
            normalized_role=fields.get("normalized_role") or "not specified",
            seniority_level=fields.get("seniority_level") or "not specified",
            department=fields.get("department") or "not specified",
            industry=fields.get("industry") or "not specified",
            skills=", ".join(fields["skills"]) if fields.get("skills") else "none",
            tools=", ".join(fields["tools"]) if fields.get("tools") else "none",
            responsibilities="\n  - ".join([""] + list(fields["responsibilities"] or [])).lstrip() or "none",
            experience_areas=", ".join(fields["experience_areas"]) if fields.get("experience_areas") else "none",
            education=fields.get("education") or "none",
            summary=fields.get("summary") or "",
        )

        max_attempts = self._settings.max_extraction_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._settings.extraction_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                raw = response.choices[0].message.content or "{}"
                parsed = json.loads(raw)
                result = DomainClassification.model_validate(parsed)
                result = self._validate_against_taxonomy(result)
                logger.info(
                    "[DOMAIN] Classified %s — domain=%s  subdomains=%s  confidence=%.2f",
                    fields.get("entity_type"),
                    result.domain_code,
                    [s.code for s in result.subdomains],
                    result.confidence,
                )
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning("[DOMAIN] Classification attempt %d failed: %s", attempt, exc)
                prompt += f"\n\nPrevious attempt failed validation: {exc}. Fix and return valid JSON."

        raise DomainClassificationError(f"Domain classification failed after {max_attempts} attempts: {last_error}")

    @staticmethod
    def _validate_against_taxonomy(result: DomainClassification) -> DomainClassification:
        if not taxonomy_service.validate_domain_code(result.domain_code):
            raise ValueError(f"Unknown domain code: {result.domain_code!r}")

        domain = taxonomy_service.get_domain(result.domain_code)
        if domain is None:
            raise ValueError(f"Domain not found: {result.domain_code!r}")

        result.domain_label = domain["label"]

        validated_subs: list = []
        for sub in result.subdomains:
            info = taxonomy_service.get_subdomain(sub.code)
            if info is None:
                logger.warning("[DOMAIN] Dropping unknown subdomain code: %s", sub.code)
                continue
            validated_subs.append(
                type(sub)(code=sub.code, label=info["label"], is_primary=sub.is_primary)
            )

        if not validated_subs:
            raise ValueError("No valid subdomain codes returned.")

        # Ensure at least one subdomain belongs to the primary domain
        domain_sub_codes = {s["code"] for s in domain.get("subdomains", [])}
        if not any(s.code in domain_sub_codes for s in validated_subs):
            raise ValueError(
                f"No subdomain belongs to primary domain {result.domain_code}. "
                f"Got: {[s.code for s in validated_subs]}"
            )

        # Ensure exactly one primary
        primaries = [s for s in validated_subs if s.is_primary]
        if not primaries:
            validated_subs[0] = type(validated_subs[0])(
                code=validated_subs[0].code,
                label=validated_subs[0].label,
                is_primary=True,
            )
        elif len(primaries) > 1:
            seen_primary = False
            fixed = []
            for s in validated_subs:
                if s.is_primary and not seen_primary:
                    seen_primary = True
                    fixed.append(s)
                else:
                    fixed.append(type(s)(code=s.code, label=s.label, is_primary=False))
            validated_subs = fixed

        result.subdomains = validated_subs
        return result


def apply_domain_to_job(job, classification: DomainClassification, source: str = "auto") -> None:
    """Copy classification fields onto a Job ORM instance."""
    job.domain_code = classification.domain_code
    job.domain_label = classification.domain_label
    job.subdomain_codes = [s.code for s in classification.subdomains]
    job.subdomain_labels = [s.label for s in classification.subdomains]
    job.domain_confidence = classification.confidence
    job.domain_source = source
    job.domain_evidence = classification.evidence


def apply_domain_to_candidate(candidate, classification: DomainClassification, source: str = "auto") -> None:
    """Copy classification fields onto a Candidate ORM instance."""
    candidate.domain_code = classification.domain_code
    candidate.domain_label = classification.domain_label
    candidate.subdomain_codes = [s.code for s in classification.subdomains]
    candidate.subdomain_labels = [s.label for s in classification.subdomains]
    candidate.domain_confidence = classification.confidence
    candidate.domain_source = source
    candidate.domain_evidence = classification.evidence


def apply_manual_domain(entity, domain_code: str, subdomain_codes: list[str], source: str = "manual") -> None:
    """Apply user-selected domain/subdomain from the taxonomy."""
    domain = taxonomy_service.get_domain(domain_code)
    if domain is None:
        raise ValueError(f"Unknown domain code: {domain_code!r}")

    valid_codes = taxonomy_service.validate_subdomain_codes(subdomain_codes)
    if not valid_codes:
        raise ValueError("At least one valid subdomain code is required.")

    domain_sub_codes = {s["code"] for s in domain.get("subdomains", [])}
    if not any(c in domain_sub_codes for c in valid_codes):
        raise ValueError(f"Subdomains must belong to domain {domain_code}.")

    labels = []
    for code in valid_codes:
        info = taxonomy_service.get_subdomain(code)
        labels.append(info["label"] if info else code)

    entity.domain_code = domain_code
    entity.domain_label = domain["label"]
    entity.subdomain_codes = valid_codes
    entity.subdomain_labels = labels
    entity.domain_confidence = 1.0
    entity.domain_source = source
    entity.domain_evidence = None
