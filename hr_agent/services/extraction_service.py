"""
LLM-based structured extraction service.

Reads raw text (from a JD or CV) and asks GPT-4o to return a strict JSON
object that is then validated with Pydantic.

Retry logic:
  On Pydantic validation failure the prompt is re-sent with the validation
  errors appended so the model can self-correct. Repeats up to
  settings.max_extraction_retries times before raising.
"""
import json
import logging
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from hr_agent.config import Settings
from hr_agent.schemas.candidate import CVExtracted
from hr_agent.schemas.job import JDExtracted

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


class ExtractionError(Exception):
    """Raised when the LLM fails to return a valid schema after all retries."""


class ExtractionService:

    def __init__(self, settings: Settings, client: OpenAI) -> None:
        self._settings = settings
        self._client = client
        self._jd_prompt_template = _load_prompt("jd_extraction.txt")
        self._cv_prompt_template = _load_prompt("cv_extraction.txt")
        logger.debug(
            "[EXTRACT] ExtractionService initialised — model: %s  max_retries: %d",
            settings.extraction_model,
            settings.max_extraction_retries,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def extract_jd(self, raw_text: str) -> JDExtracted:
        logger.info(
            "[EXTRACT] Starting JD extraction — input length: %d chars  model: %s",
            len(raw_text),
            self._settings.extraction_model,
        )
        result = self._extract_with_retry(
            prompt_template=self._jd_prompt_template,
            raw_text=raw_text,
            schema=JDExtracted,
            entity_label="JD",
        )
        logger.info(
            "[EXTRACT] JD extracted ✓ — title=%r  role=%r  exp=%s–%s  "
            "must_have=%s (%d skills)  industry=%r",
            result.title,
            result.normalized_role,
            result.experience_min,
            result.experience_max,
            result.must_have_skills,
            len(result.must_have_skills),
            result.industry,
        )
        return result

    def extract_cv(self, raw_text: str) -> CVExtracted:
        logger.info(
            "[EXTRACT] Starting CV extraction — input length: %d chars  model: %s",
            len(raw_text),
            self._settings.extraction_model,
        )
        result = self._extract_with_retry(
            prompt_template=self._cv_prompt_template,
            raw_text=raw_text,
            schema=CVExtracted,
            entity_label="CV",
        )
        logger.info(
            "[EXTRACT] CV extracted ✓ — name=%r  role=%r  exp=%s yrs  "
            "skills=%s (%d total)  industries=%s",
            result.candidate_name,
            result.normalized_role,
            result.years_experience,
            result.skills[:5],   # first 5 skills to avoid log spam
            len(result.skills),
            result.industries,
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_with_retry(
        self,
        prompt_template: str,
        raw_text: str,
        schema: type[JDExtracted | CVExtracted],
        entity_label: str,
    ) -> JDExtracted | CVExtracted:
        max_attempts = self._settings.max_extraction_retries + 1
        # Use plain replace instead of str.format() — prompts contain JSON schema
        # examples with {curly braces} that are NOT format placeholders.
        base_prompt = prompt_template.replace("{raw_text}", raw_text)
        prompt = base_prompt
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            logger.debug(
                "[EXTRACT] %s — attempt %d/%d", entity_label, attempt, max_attempts
            )

            raw_json = self._call_llm(prompt)
            logger.debug("[EXTRACT] Raw LLM response:\n  %s", raw_json[:500])

            try:
                parsed = json.loads(raw_json)
                validated = schema.model_validate(parsed)
                logger.info(
                    "[EXTRACT] %s extraction succeeded on attempt %d/%d.",
                    entity_label, attempt, max_attempts,
                )
                return validated

            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning(
                    "[EXTRACT] %s attempt %d/%d failed validation:\n  %s",
                    entity_label, attempt, max_attempts, exc,
                )
                if attempt < max_attempts:
                    logger.info(
                        "[EXTRACT] Retrying %s with validation errors appended to prompt.",
                        entity_label,
                    )
                    prompt = (
                        f"{base_prompt}\n\n"
                        f"Your previous response was invalid. Errors:\n{exc}\n\n"
                        "Please fix the JSON and return only the corrected object."
                    )

        raise ExtractionError(
            f"{entity_label} extraction failed after {max_attempts} attempts. "
            f"Last error: {last_error}"
        )

    def _call_llm(self, prompt: str) -> str:
        logger.debug(
            "[EXTRACT] Calling %s — prompt length: %d chars",
            self._settings.extraction_model, len(prompt),
        )
        response = self._client.chat.completions.create(
            model=self._settings.extraction_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        usage = response.usage
        if usage:
            logger.info(
                "[EXTRACT] LLM usage — prompt_tokens: %d  completion_tokens: %d  total: %d",
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
            )
        return response.choices[0].message.content or "{}"
