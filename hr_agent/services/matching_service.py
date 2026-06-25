"""
Matching engine — the core of the HR Agent.

Four-stage pipeline:
  1. Hard filters  — eliminate candidates that fail mandatory criteria
  2. Rule score    — weighted sub-scores (skill, experience, role, industry)
  3. Vector score  — cosine similarity of summary embeddings
  4. LLM rerank    — GPT-4o holistic relevance score 0–100
  Final score      = 0.4×rule + 0.2×vector + 0.4×llm  (weights configurable)
"""
import json
import logging
import re
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session

from hr_agent.config import Settings
from hr_agent.models.candidate import Candidate
from hr_agent.models.job import Job
from hr_agent.models.match_result import MatchResult
from hr_agent.schemas.match import LLMRankItem
from hr_agent.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ── Pure scoring functions (no I/O — easy to unit-test) ───────────────────────

def jaccard_skill_score(candidate_skills: list[str], required_skills: list[str]) -> float:
    """
    Fraction of required skills/tools the candidate possesses (case-insensitive).

    Both `candidate_skills` and `required_skills` should already be combined lists:
      candidate side → skills + tools_and_technologies
      job side       → must_have_skills + tools_and_technologies
    """
    if not required_skills:
        return 1.0
    cand = {s.lower().strip() for s in (candidate_skills or [])}
    req = {s.lower().strip() for s in required_skills}
    return len(cand & req) / len(req)


def experience_band_score(
    years: float | None, exp_min: int | None, exp_max: int | None
) -> float:
    """
    1.0  — candidate is inside [min, max].
    0.5  — experience unknown (partial credit).
    Degrades linearly at 0.25/yr below min, 0.20/yr above max, floor 0.
    """
    if years is None:
        return 0.5
    if exp_min is None and exp_max is None:
        return 1.0
    if exp_min is not None and years < exp_min:
        return max(0.0, 1.0 - (exp_min - years) * 0.25)
    if exp_max is not None and years > exp_max:
        return max(0.0, 1.0 - (years - exp_max) * 0.20)
    return 1.0


_ROLE_STOP_WORDS = frozenset({
    "a", "an", "and", "for", "in", "of", "or", "the", "to", "with",
})


def _role_tokens(role: str) -> set[str]:
    """Tokenise a free-form role label for semantic overlap scoring."""
    cleaned = re.sub(r"[_\-/]", " ", role.lower())
    return {
        token
        for token in re.split(r"[^\w]+", cleaned)
        if len(token) > 2 and token not in _ROLE_STOP_WORDS
    }


def role_match_score(candidate_role: str | None, job_role: str | None) -> float:
    """
    Semantic overlap between free-form role labels.

    Exact match → 1.0. Token Jaccard + substring checks for related wording
    (e.g. 'Senior Backend Engineer' vs 'Backend Software Engineer').
    """
    if not candidate_role or not job_role:
        return 0.5

    cand = candidate_role.strip()
    job = job_role.strip()
    if cand.lower() == job.lower():
        return 1.0

    cand_norm = cand.lower().replace("_", " ")
    job_norm = job.lower().replace("_", " ")
    if cand_norm in job_norm or job_norm in cand_norm:
        return 0.9

    cand_tokens = _role_tokens(cand)
    job_tokens = _role_tokens(job)
    if not cand_tokens or not job_tokens:
        return 0.5

    overlap = cand_tokens & job_tokens
    union = cand_tokens | job_tokens
    return round(len(overlap) / len(union), 4)


def industry_match_score(
    candidate_industries: list[str], job_industry: str | None
) -> float:
    if not job_industry:
        return 1.0
    if not candidate_industries:
        return 0.0
    normalised = {i.lower().strip() for i in candidate_industries}
    return 1.0 if job_industry.lower().strip() in normalised else 0.0


def compute_rule_score(candidate: Candidate, job: Job, weights) -> float:
    # Merge skills + tools for broader coverage on both sides
    cand_combined = (candidate.skills or []) + (candidate.tools_and_technologies or [])
    job_combined = (job.must_have_skills or []) + (job.tools_and_technologies or [])
    skill = jaccard_skill_score(cand_combined, job_combined)
    exp = experience_band_score(
        candidate.years_experience, job.experience_min, job.experience_max
    )
    role = role_match_score(candidate.normalized_role, job.normalized_role)
    ind = industry_match_score(candidate.industries or [], job.industry)
    return round(
        weights.skill * skill
        + weights.experience * exp
        + weights.role * role
        + weights.industry * ind,
        4,
    )


def passes_hard_filter(candidate: Candidate, job: Job) -> tuple[bool, str]:
    """
    Return (True, "") on pass or (False, reason) on fail.

    Always applied:
      - Experience band check (min/max years).

    Conditionally applied (only when user has configured per-JD hard checks):
      List fields — every selected item must appear in the candidate's pool:
        must_have_skills       → candidate skills + tools_and_technologies
        tools_and_technologies → candidate tools_and_technologies
        certifications         → candidate certifications
        education_requirements → candidate education degree/institution text

      Scalar fields — candidate's value must match the required value (when non-empty):
        seniority_level   → exact match (case-insensitive)
        normalized_role   → semantic overlap (free-form labels, not exact codes)
        industry          → candidate's industries list must contain it
        location          → substring match in either direction

    Skill matching is NOT included as a default hard filter because must_have_skills
    are often described with semantically equivalent but differently worded terms.
    Users can explicitly promote specific skills to hard checks via the UI.
    """
    # ── Experience band (always enforced) ─────────────────────────────────────
    years = candidate.years_experience
    if job.experience_min is not None and years is not None and years < job.experience_min:
        return False, f"experience {years}yr is below minimum {job.experience_min}yr"
    if job.experience_max is not None and years is not None and years > job.experience_max:
        return False, f"experience {years}yr exceeds maximum {job.experience_max}yr"

    # ── User-configured hard checks (per-JD) ──────────────────────────────────
    hard_checks: dict = job.hard_checks or {}
    if not hard_checks:
        return True, ""

    # Build candidate lookup pools once (lower-cased)
    cand_skill_pool = {
        s.lower().strip()
        for s in (candidate.skills or []) + (candidate.tools_and_technologies or [])
    }
    cand_tools = {s.lower().strip() for s in (candidate.tools_and_technologies or [])}
    cand_certs = {s.lower().strip() for s in (candidate.certifications or [])}
    cand_industries = {i.lower().strip() for i in (candidate.industries or [])}
    cand_education_strings = [
        f"{edu.get('degree') or ''} {edu.get('institution') or ''}".lower().strip()
        for edu in (candidate.education or [])
        if isinstance(edu, dict)
    ]

    LIST_FIELD_POOLS = {
        "must_have_skills": cand_skill_pool,
        "tools_and_technologies": cand_tools,
        "certifications": cand_certs,
    }

    for field, required in hard_checks.items():
        if not required:
            continue

        if field == "education_requirements":
            items = required if isinstance(required, list) else [required]
            for item in items:
                req = str(item).lower().strip()
                if not req:
                    continue
                if not any(req in edu_text for edu_text in cand_education_strings):
                    return False, f"missing hard-required education: '{item}'"
            continue

        if field in LIST_FIELD_POOLS:
            pool = LIST_FIELD_POOLS[field]
            items = required if isinstance(required, list) else [required]
            for item in items:
                if item.lower().strip() not in pool:
                    return False, f"missing hard-required {field}: '{item}'"

        elif field == "seniority_level":
            cand_val = (candidate.seniority_level or "").lower().strip()
            req_val = str(required).lower().strip()
            if cand_val and req_val and cand_val != req_val:
                return (
                    False,
                    f"seniority mismatch: required '{required}', "
                    f"candidate has '{candidate.seniority_level}'",
                )

        elif field == "normalized_role":
            cand_val = (candidate.normalized_role or "").strip()
            req_val = str(required).strip()
            if cand_val and req_val and role_match_score(cand_val, req_val) < 0.35:
                return (
                    False,
                    f"role mismatch: required '{required}', "
                    f"candidate has '{candidate.normalized_role}'",
                )

        elif field == "industry":
            req_val = str(required).lower().strip()
            if req_val and cand_industries and req_val not in cand_industries:
                return (
                    False,
                    f"industry mismatch: required '{required}', "
                    f"candidate has {sorted(candidate.industries or [])}",
                )

        elif field == "location":
            cand_val = (candidate.location or "").lower().strip()
            req_val = str(required).lower().strip()
            if cand_val and req_val:
                if req_val not in cand_val and cand_val not in req_val:
                    return (
                        False,
                        f"location mismatch: required '{required}', "
                        f"candidate has '{candidate.location}'",
                    )

    return True, ""


# ── Service class ──────────────────────────────────────────────────────────────

class MatchingService:

    def __init__(
        self,
        settings: Settings,
        client: OpenAI,
        embedding_service: EmbeddingService,
    ) -> None:
        self._settings = settings
        self._client = client
        self._embedding_svc = embedding_service
        self._rerank_prompt = _load_prompt("reranking.txt")

    # ── Public interface ──────────────────────────────────────────────────────

    def run(
        self,
        db: Session,
        job_id: str,
        source_filter: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[MatchResult]:
        """
        Execute the full pipeline for `job_id`.
        Deletes previous results for this job first — re-running is always safe.
        Optional source_filter limits which candidates are considered by source.
        Optional top_k truncates the final ranked list.
        """
        logger.info("=" * 60)
        logger.info("[MATCH] Starting pipeline for job: %s", job_id)
        logger.info("=" * 60)

        job = self._get_job(db, job_id)
        logger.info(
            "[MATCH] Job loaded — title=%r  role=%r  seniority=%r  exp=%s–%s  "
            "must_have=%s  tools=%s  industry=%r",
            job.title, job.normalized_role, job.seniority_level,
            job.experience_min, job.experience_max,
            job.must_have_skills, job.tools_and_technologies, job.industry,
        )

        query = db.query(Candidate).filter(Candidate.normalized_role.isnot(None))
        if source_filter:
            query = query.filter(Candidate.source_name.in_(source_filter))
            logger.info("[MATCH] source_filter=%s applied.", source_filter)
        candidates = query.all()
        if not candidates:
            logger.warning("[MATCH] No structured candidates in DB — returning empty results.")
            return []

        logger.info("[MATCH] Found %d structured candidates to evaluate.", len(candidates))
        cand_map: dict[str, Candidate] = {c.email: c for c in candidates}

        # Clear stale results
        deleted = db.query(MatchResult).filter_by(job_id=job_id).delete()
        if deleted:
            logger.info("[MATCH] Cleared %d stale match results.", deleted)
        db.commit()

        # ── Stage 1: Hard filters ──────────────────────────────────────────
        logger.info("[MATCH] ── Stage 1: Hard Filters ──────────────────────")
        all_results: list[MatchResult] = []
        for candidate in candidates:
            passed, reason = passes_hard_filter(candidate, job)
            if passed:
                logger.info(
                    "[FILTER] ✓ PASS  %s (%s) — %s yrs  skills: %s",
                    candidate.name or candidate.email,
                    candidate.email,
                    candidate.years_experience,
                    candidate.skills,
                )
            else:
                logger.info(
                    "[FILTER] ✗ FAIL  %s (%s) — reason: %s",
                    candidate.name or candidate.email,
                    candidate.email,
                    reason,
                )
            all_results.append(
                MatchResult(
                    job_id=job_id,
                    candidate_id=candidate.email,
                    is_filtered=not passed,
                    filter_reason=reason or None,
                )
            )

        passing = [r for r in all_results if not r.is_filtered]
        logger.info(
            "[FILTER] Result: %d/%d passed hard filter, %d eliminated.",
            len(passing), len(all_results), len(all_results) - len(passing),
        )

        if not passing:
            logger.warning("[MATCH] All candidates eliminated — no scoring performed.")
            self._persist(db, all_results)
            return all_results

        # ── Stage 2: Rule scores ───────────────────────────────────────────
        logger.info("[MATCH] ── Stage 2: Rule Scores ───────────────────────")
        rule_weights = self._settings.rule_sub_weights
        logger.debug(
            "[RULE] Weights — skill=%.2f  exp=%.2f  role=%.2f  industry=%.2f",
            rule_weights.skill, rule_weights.experience,
            rule_weights.role, rule_weights.industry,
        )
        job_combined = (job.must_have_skills or []) + (job.tools_and_technologies or [])
        logger.debug(
            "[RULE] JD combined (must_have + tools) for Jaccard scoring: %s", job_combined
        )

        for result in passing:
            c = cand_map[result.candidate_id]
            cand_combined = (c.skills or []) + (c.tools_and_technologies or [])
            skill = jaccard_skill_score(cand_combined, job_combined)
            exp = experience_band_score(c.years_experience, job.experience_min, job.experience_max)
            role = role_match_score(c.normalized_role, job.normalized_role)
            ind = industry_match_score(c.industries or [], job.industry)
            result.rule_score = round(
                rule_weights.skill * skill
                + rule_weights.experience * exp
                + rule_weights.role * role
                + rule_weights.industry * ind,
                4,
            )
            logger.info(
                "[RULE]  %s (%s) — skill_jaccard=%.2f  exp=%.2f  role=%.2f  ind=%.2f  → rule_score=%.4f",
                c.name or c.email, c.email, skill, exp, role, ind, result.rule_score,
            )
            logger.debug(
                "[RULE]  %s — cand_combined=%s  jd_combined=%s",
                c.name or c.email, cand_combined, job_combined
            )

        # ── Stage 3: Vector scores ─────────────────────────────────────────
        logger.info("[MATCH] ── Stage 3: Vector Scores ─────────────────────")
        self._apply_vector_scores(db, job, passing, cand_map)

        # ── Stage 4: LLM rerank on top-N ──────────────────────────────────
        logger.info("[MATCH] ── Stage 4: LLM Rerank ────────────────────────")
        top_n = sorted(
            passing,
            key=lambda r: (r.rule_score or 0.0) + (r.vector_score or 0.0),
            reverse=True,
        )[: self._settings.top_n_for_rerank]

        logger.info(
            "[RERANK] Sending top %d candidates (of %d) to %s for reranking.",
            len(top_n), len(passing), self._settings.rerank_model,
        )
        self._apply_llm_scores(job, top_n, cand_map)

        # ── Final score ────────────────────────────────────────────────────
        logger.info("[MATCH] ── Final Scores ────────────────────────────────")
        sw = self._settings.score_weights
        logger.debug(
            "[FINAL] Score weights — rule=%.2f  vector=%.2f  llm=%.2f",
            sw.rule, sw.vector, sw.llm,
        )

        for result in top_n:
            result.final_score = round(
                sw.rule * (result.rule_score or 0.0)
                + sw.vector * (result.vector_score or 0.0)
                + sw.llm * (result.llm_score or 0.0),
                4,
            )
            c = cand_map[result.candidate_id]
            logger.info(
                "[FINAL] %s (%s) — rule=%.4f  vector=%.4f  llm=%.4f  → final_score=%.4f",
                c.name or c.email, c.email,
                result.rule_score or 0, result.vector_score or 0,
                result.llm_score or 0, result.final_score,
            )

        # Sort and log ranking summary
        ranked = sorted(
            [r for r in top_n if r.final_score is not None],
            key=lambda r: r.final_score,
            reverse=True,
        )
        logger.info("[MATCH] ── Final Ranking Summary ──────────────────────")
        for rank, result in enumerate(ranked, 1):
            c = cand_map[result.candidate_id]
            logger.info(
                "[RANKING] #%d  %s (%s)  final=%.4f  explanation: %s",
                rank,
                c.name or c.email,
                c.email,
                result.final_score,
                (result.explanation or "—")[:100],
            )

        if top_k is not None:
            ranked = ranked[:top_k]
            logger.info("[MATCH] top_k=%d applied — returning %d results.", top_k, len(ranked))

        self._persist(db, all_results)
        logger.info(
            "[MATCH] Pipeline complete — %d ranked, %d filtered. Job: %s",
            len(ranked), len(all_results) - len(passing), job_id,
        )
        logger.info("=" * 60)
        return all_results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_job(self, db: Session, job_id: str) -> Job:
        job = db.query(Job).filter_by(id=job_id).first()
        if job is None:
            logger.error("[MATCH] Job %r not found in DB.", job_id)
            raise ValueError(f"Job {job_id!r} not found.")
        if job.normalized_role is None:
            logger.error(
                "[MATCH] Job %r has not been extracted yet (normalized_role is NULL).", job_id
            )
            raise ValueError(
                f"Job {job_id!r} has not been extracted yet. "
                "Wait for processing status STRUCTURED before running matching."
            )
        return job

    def _apply_vector_scores(
        self,
        db: Session,
        job: Job,
        passing: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        job_vec = self._embedding_svc.load_vector(db, "job", job.id)
        if job_vec is None:
            logger.warning(
                "[VECTOR] No embedding for job %s — setting vector_score=0 for all.", job.id
            )
            for r in passing:
                r.vector_score = 0.0
            return

        for result in passing:
            c = cand_map[result.candidate_id]
            cand_vec = self._embedding_svc.load_vector(db, "candidate", result.candidate_id)
            if cand_vec is None:
                result.vector_score = 0.0
                logger.warning(
                    "[VECTOR] No embedding for candidate %s — vector_score=0.", result.candidate_id
                )
            else:
                result.vector_score = round(
                    EmbeddingService.cosine_similarity(job_vec, cand_vec), 4
                )
                logger.info(
                    "[VECTOR] %s (%s) → vector_score=%.4f",
                    c.name or c.email, c.email, result.vector_score,
                )

    def _apply_llm_scores(
        self,
        job: Job,
        top_results: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        candidates_block = self._build_candidates_block(top_results, cand_map)
        prompt = self._rerank_prompt.format(
            title=job.title or "",
            normalized_role=job.normalized_role or "",
            seniority_level=job.seniority_level or "not specified",
            experience_min=job.experience_min if job.experience_min is not None else "not specified",
            experience_max=job.experience_max if job.experience_max is not None else "not specified",
            employment_type=job.employment_type or "not specified",
            location=job.location or "not specified",
            must_have_skills=", ".join(job.must_have_skills or []),
            good_to_have_skills=", ".join(job.good_to_have_skills or []),
            tools_and_technologies=", ".join(job.tools_and_technologies or []),
            education_requirements=", ".join(job.education_requirements or []),
            certifications=", ".join(job.certifications or []),
            responsibilities="\n  - ".join([""] + (job.responsibilities or [])).lstrip(),
            industry=job.industry or "not specified",
            summary=job.summary or "",
            candidates_block=candidates_block,
        )

        logger.debug("[RERANK] Prompt length: %d chars", len(prompt))
        raw = self._call_rerank_llm(prompt)
        logger.debug("[RERANK] Raw LLM response:\n  %s", raw[:800])

        score_map = self._parse_rerank_response(raw, top_results)

        for result in top_results:
            item = score_map.get(result.candidate_id)
            c = cand_map.get(result.candidate_id)
            if item:
                result.llm_score = round(item.score / 100.0, 4)
                result.explanation = item.explanation
                logger.info(
                    "[RERANK] %s (%s) → llm_score=%d/100  explanation: %s",
                    c.name if c else result.candidate_id,
                    result.candidate_id,
                    item.score,
                    item.explanation[:120],
                )
            else:
                result.llm_score = 0.0
                logger.warning(
                    "[RERANK] No score returned for candidate %s — llm_score=0.",
                    result.candidate_id,
                )

    def _call_rerank_llm(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._settings.rerank_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        usage = response.usage
        if usage:
            logger.info(
                "[RERANK] LLM usage — prompt_tokens: %d  completion_tokens: %d  total: %d",
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
            )
        return response.choices[0].message.content or "{}"

    def _parse_rerank_response(
        self,
        raw: str,
        top_results: list[MatchResult],
    ) -> dict[str, LLMRankItem]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("[RERANK] Response is not valid JSON: %.300s", raw)
            return {}

        # Unwrap {"rankings": [...]} or similar dict wrappers
        if isinstance(parsed, dict):
            for key in ("rankings", "results", "candidates", "scores"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                parsed = list(parsed.values())[0] if parsed else []

        if not isinstance(parsed, list):
            logger.error("[RERANK] Unexpected shape: %s — expected list.", type(parsed).__name__)
            return {}

        valid_ids = {r.candidate_id for r in top_results}
        score_map: dict[str, LLMRankItem] = {}
        for item in parsed:
            try:
                ranked = LLMRankItem.model_validate(item)
                if ranked.candidate_id in valid_ids:
                    score_map[ranked.candidate_id] = ranked
                else:
                    logger.debug(
                        "[RERANK] Ignoring unknown candidate_id %r in LLM response.",
                        ranked.candidate_id,
                    )
            except ValidationError as exc:
                logger.warning("[RERANK] Skipping malformed item %s: %s", item, exc)

        logger.info(
            "[RERANK] Parsed %d/%d scores from LLM response.",
            len(score_map), len(top_results),
        )
        return score_map

    @staticmethod
    def _build_candidates_block(
        results: list[MatchResult], cand_map: dict[str, Candidate]
    ) -> str:
        sections = []
        for result in results:
            c = cand_map.get(result.candidate_id)
            if c is None:
                continue

            # Build employment history as compact bullet list
            emp_history = c.employment_history or []
            history_lines = "; ".join(
                f"{e.get('title', '?')} @ {e.get('company', '?')} "
                f"({e.get('start_date', '?')} – {e.get('end_date', 'present')})"
                for e in emp_history[:4]
            ) or "not available"

            # Education compact representation
            education = c.education or []
            edu_lines = "; ".join(
                f"{e.get('degree', '')} {e.get('institution', '')}".strip()
                for e in education[:3]
            ) or "not available"

            sections.append(
                f"candidate_id          : {c.email}\n"
                f"name                  : {c.name or 'unknown'}\n"
                f"current_title         : {c.current_title or 'unknown'}\n"
                f"current_company       : {c.current_company or 'unknown'}\n"
                f"normalized_role       : {c.normalized_role or 'unknown'}\n"
                f"seniority_level       : {c.seniority_level or 'unknown'}\n"
                f"location              : {c.location or 'unknown'}\n"
                f"years_experience      : {c.years_experience if c.years_experience is not None else 'unknown'}\n"
                f"skills                : {', '.join(c.skills or [])}\n"
                f"tools_and_technologies: {', '.join(c.tools_and_technologies or [])}\n"
                f"certifications        : {', '.join(c.certifications or [])}\n"
                f"experience_areas      : {', '.join(c.experience_areas or [])}\n"
                f"responsibilities      : {', '.join((c.responsibilities or [])[:5])}\n"
                f"employment_history    : {history_lines}\n"
                f"education             : {edu_lines}\n"
                f"industries            : {', '.join(c.industries or [])}\n"
                f"summary               : {c.summary or ''}"
            )
        return "\n---\n".join(sections)

    @staticmethod
    def _persist(db: Session, results: list[MatchResult]) -> None:
        for result in results:
            db.add(result)
        db.commit()
        logger.debug("[MATCH] Persisted %d match results to DB.", len(results))
