"""
Matching engine — the core of the HR Agent.

Pipeline (Phase 4):
  0. Pool scope        — only in-pool candidates (when match_pool_only=true)
  1. Requirement fit   — ontology-normalized hard checks
  2. Rule score        — structured sub-scores (debug / legacy breakdown)
  3. Retrieval score   — fingerprint embedding cosine similarity (bi-encoder)
  4. Cross-encoder     — joint job–candidate rerank on top-N (precision)
  5. LLM explanation — narrative only (no score impact when llm_explanation_only)
  Final score          = 25% fit + 25% retrieval + 50% rerank (configurable)
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
from hr_agent.models.job_candidate_pool import JobCandidatePool
from hr_agent.models.match_result import MatchResult
from hr_agent.schemas.match import LLMRankItem
from hr_agent.services.cross_encoder_service import CrossEncoderService
from hr_agent.services.embedding_service import EmbeddingService
from hr_agent.services import ontology_service
from hr_agent.services.profile_fingerprint_service import (
    build_candidate_fingerprint,
    build_job_fingerprint,
)
from hr_agent.services.requirement_fit_service import evaluate_requirement_fit

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ── Pure scoring functions (no I/O — easy to unit-test) ───────────────────────

def ontology_skill_score(candidate_skills: list[str], required_skills: list[str]) -> float:
    """
    Ontology-aware coverage of required skills/tools/certs.
    Handles synonyms (Node → Node.js, Postgres → PostgreSQL, etc.).
    """
    return ontology_service.list_coverage_score(required_skills, candidate_skills)


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
    skill = ontology_skill_score(cand_combined, job_combined)
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

    Uses ontology-normalized matching for skills, tools, certifications, and
    education (Phase 3). Experience band is always enforced.
    """
    result = evaluate_requirement_fit(candidate, job)
    return result.passed, result.filter_reason


# ── Service class ──────────────────────────────────────────────────────────────

class MatchingService:

    def __init__(
        self,
        settings: Settings,
        client: OpenAI,
        embedding_service: EmbeddingService,
        cross_encoder_service: CrossEncoderService | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._embedding_svc = embedding_service
        self._cross_encoder_svc = cross_encoder_service or CrossEncoderService(settings)
        self._explanation_prompt = _load_prompt("explanation.txt")
        self._rerank_prompt = _load_prompt("reranking.txt")

    # ── Public interface ──────────────────────────────────────────────────────

    def run(
        self,
        db: Session,
        job_id: str,
        source_filter: list[str] | None = None,
        top_k: int | None = None,
        refresh: bool = False,
    ) -> list[MatchResult]:
        """
        Execute the full pipeline for `job_id`.
        When refresh=True, deletes all previous results and re-runs from scratch.
        When match_pool_only is enabled, only candidates in the job pool are evaluated.
        Optional source_filter limits which candidates are considered by source.
        Optional top_k truncates the final ranked list.
        """
        logger.info("=" * 60)
        logger.info("[MATCH] Starting pipeline for job: %s (refresh=%s)", job_id, refresh)
        logger.info("=" * 60)

        job = self._get_job(db, job_id)

        if refresh:
            deleted = db.query(MatchResult).filter_by(job_id=job_id).delete()
            if deleted:
                logger.info("[MATCH] Cleared %d stale match results (refresh).", deleted)
            db.commit()

        existing_results = db.query(MatchResult).filter_by(job_id=job_id).all()
        existing_results_map = {r.candidate_id: r for r in existing_results}

        query = db.query(Candidate)
        # Candidates must have either a normalized_role (LLM-extracted) or at
        # minimum a current_title (Zoho direct-sync). For direct Zoho candidates
        # that were synced before we started writing normalized_role, backfill it
        # inline from current_title so they are included in this match run.
        query = query.filter(
            (Candidate.normalized_role.isnot(None)) |
            (Candidate.current_title.isnot(None))
        )
        if source_filter:
            query = query.filter(Candidate.source_name.in_(source_filter))
            logger.info("[MATCH] source_filter=%s applied.", source_filter)

        # ── Pool scope (Phase 2+3) ───────────────────────────────────────────

        if self._settings.match_pool_only:
            pool_rows = (
                db.query(JobCandidatePool)
                .filter(
                    JobCandidatePool.job_id == job_id,
                    JobCandidatePool.pool_status.in_(("in_pool", "manual_add")),
                )
                .all()
            )
            if pool_rows:
                pool_ids = {r.candidate_id for r in pool_rows}
                query = query.filter(Candidate.email.in_(pool_ids))
                logger.info("[MATCH] Pool scope — %d candidates in pool.", len(pool_ids))
            elif job.domain_code:
                raise ValueError(
                    f"Job {job_id!r} has a domain but no candidate pool. "
                    "Build the pool on the position page before running matching."
                )
            else:
                logger.warning(
                    "[MATCH] match_pool_only=true but no domain/pool — evaluating all candidates."
                )

        candidates = query.all()
        if not candidates:
            logger.warning("[MATCH] No candidates to evaluate — returning existing results.")
            return existing_results

        new_candidates = [c for c in candidates if c.email not in existing_results_map]
        if not new_candidates and existing_results:
            logger.info("[MATCH] All %d candidates already processed.", len(candidates))
            logger.info("=" * 60)
            return existing_results

        logger.info(
            "[MATCH] Processing %d candidates (%d new, %d existing).",
            len(new_candidates), len(new_candidates), len(existing_results),
        )
        cand_map: dict[str, Candidate] = {c.email: c for c in new_candidates}

        # ── Stage 1: Requirement fit / hard filters ──────────────────────────
        logger.info("[MATCH] ── Stage 1: Requirement Fit (ontology) ───────────")
        all_results: list[MatchResult] = []
        for candidate in new_candidates:
            fit = evaluate_requirement_fit(candidate, job)
            passed = fit.passed
            reason = fit.filter_reason
            if passed:
                logger.info(
                    "[FILTER] ✓ PASS  %s (%s) — fit=%.2f",
                    candidate.name or candidate.email, candidate.email, fit.score,
                )
            else:
                logger.info(
                    "[FILTER] ✗ FAIL  %s (%s) — reason: %s  gaps: %s",
                    candidate.name or candidate.email, candidate.email, reason, fit.gaps,
                )
            all_results.append(
                MatchResult(
                    job_id=job_id,
                    candidate_id=candidate.email,
                    is_filtered=not passed,
                    filter_reason=reason or None,
                    requirement_fit_score=fit.score,
                    requirement_gaps=fit.gaps or None,
                )
            )

        passing = [r for r in all_results if not r.is_filtered]
        logger.info(
            "[FILTER] Result: %d/%d passed hard filter, %d eliminated.",
            len(passing), len(all_results), len(all_results) - len(passing),
        )

        if not passing:
            logger.warning("[MATCH] All new candidates eliminated — no scoring performed.")
            self._persist(db, all_results)
            combined_results = existing_results + all_results
            logger.info("=" * 60)
            return combined_results

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
            skill = ontology_skill_score(cand_combined, job_combined)
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
                "[RULE]  %s (%s) — skill_ont=%.2f  exp=%.2f  role=%.2f  ind=%.2f  → rule_score=%.4f",
                c.name or c.email, c.email, skill, exp, role, ind, result.rule_score,
            )
            logger.debug(
                "[RULE]  %s — cand_combined=%s  jd_combined=%s",
                c.name or c.email, cand_combined, job_combined
            )

        # ── Stage 3: Fingerprint retrieval (bi-encoder) ────────────────────
        logger.info("[MATCH] ── Stage 3: Fingerprint Retrieval ─────────────")
        self._apply_retrieval_scores(db, job, passing, cand_map)

        # ── Stage 4: Cross-encoder rerank on top-N ─────────────────────────
        logger.info("[MATCH] ── Stage 4: Cross-Encoder Rerank ──────────────")
        rerank_candidates = sorted(
            passing,
            key=lambda r: r.vector_score or 0.0,
            reverse=True,
        )[: self._settings.top_n_for_rerank]

        logger.info(
            "[RERANK-CE] Reranking top %d candidates (of %d) with cross-encoder.",
            len(rerank_candidates), len(passing),
        )
        self._apply_cross_encoder_scores(job, rerank_candidates, cand_map)

        # ── Final score + LLM ──────────────────────────────────────────────
        logger.info("[MATCH] ── Final Scores ────────────────────────────────")

        if self._settings.llm_explanation_only:
            fsw = self._settings.final_score_weights
            for result in rerank_candidates:
                fit = result.requirement_fit_score or 0.0
                retrieval = result.vector_score or 0.0
                rerank = result.rerank_score or 0.0
                result.final_score = round(
                    fsw.requirement_fit * fit
                    + fsw.retrieval * retrieval
                    + fsw.rerank * rerank,
                    4,
                )
                c = cand_map[result.candidate_id]
                logger.info(
                    "[FINAL] %s (%s) — fit=%.4f  retrieval=%.4f  rerank=%.4f  → final=%.4f",
                    c.name or c.email, c.email, fit, retrieval, rerank, result.final_score,
                )

            ranked = sorted(
                [r for r in rerank_candidates if r.final_score is not None],
                key=lambda r: r.final_score,
                reverse=True,
            )

            explain_n = ranked[: self._settings.llm_explanation_top_n]
            logger.info(
                "[MATCH] ── Stage 5: LLM Explanations (%d candidates) ─────",
                len(explain_n),
            )
            self._apply_llm_explanations(job, explain_n, cand_map)
        else:
            logger.info("[MATCH] ── Stage 5: LLM Rerank (legacy scoring) ───")
            self._apply_llm_scores(job, rerank_candidates, cand_map)
            sw = self._settings.score_weights
            for result in rerank_candidates:
                result.final_score = round(
                    sw.rule * (result.rule_score or 0.0)
                    + sw.vector * (result.vector_score or 0.0)
                    + sw.llm * (result.llm_score or 0.0),
                    4,
                )
            ranked = sorted(
                [r for r in rerank_candidates if r.final_score is not None],
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
        
        combined_results = existing_results + all_results
        
        logger.info(
            "[MATCH] Pipeline complete — %d ranked, %d filtered new candidates. Total results: %d. Job: %s",
            len(ranked), len(all_results) - len(passing), len(combined_results), job_id,
        )
        logger.info("=" * 60)
        return combined_results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_job(self, db: Session, job_id: str) -> Job:
        job = db.query(Job).filter_by(id=job_id).first()
        if job is None:
            logger.error("[MATCH] Job %r not found in DB.", job_id)
            raise ValueError(f"Job {job_id!r} not found.")
        if job.normalized_role is None:
            # For Zoho-synced jobs the LLM extraction may not have run yet.
            # Fall back to the job title as the role label — it is descriptive
            # enough for role_match_score, which already handles freeform labels.
            if job.title:
                logger.warning(
                    "[MATCH] Job %r has no normalized_role — using title %r as fallback.",
                    job_id, job.title,
                )
                job.normalized_role = job.title
                db.commit()
            else:
                logger.error(
                    "[MATCH] Job %r has no normalized_role and no title — cannot run matching.", job_id
                )
                raise ValueError(
                    f"Job {job_id!r} has no title or normalized_role. "
                    "Please add a title or wait for LLM extraction to complete."
                )
        return job

    def _apply_retrieval_scores(
        self,
        db: Session,
        job: Job,
        passing: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        job_fp = build_job_fingerprint(job)
        job_vec = self._embedding_svc.ensure_fingerprint_embedding(
            db, "job", job.id, job_fp
        )
        if job_vec is None:
            logger.warning("[RETRIEVAL] No fingerprint embedding for job %s.", job.id)
            for r in passing:
                r.vector_score = 0.0
            return

        for result in passing:
            c = cand_map[result.candidate_id]
            cand_fp = build_candidate_fingerprint(c)
            cand_vec = self._embedding_svc.ensure_fingerprint_embedding(
                db, "candidate", result.candidate_id, cand_fp
            )
            if cand_vec is None:
                result.vector_score = 0.0
                logger.warning(
                    "[RETRIEVAL] No fingerprint embedding for %s.", result.candidate_id
                )
            else:
                result.vector_score = round(
                    EmbeddingService.cosine_similarity(job_vec, cand_vec), 4
                )
                logger.info(
                    "[RETRIEVAL] %s (%s) → retrieval_score=%.4f",
                    c.name or c.email, c.email, result.vector_score,
                )
        db.commit()

    def _apply_cross_encoder_scores(
        self,
        job: Job,
        results: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        if not results:
            return

        job_fp = build_job_fingerprint(job)
        cand_fps = [
            build_candidate_fingerprint(cand_map[r.candidate_id])
            for r in results
            if r.candidate_id in cand_map
        ]
        if len(cand_fps) != len(results):
            logger.warning("[RERANK-CE] Candidate map mismatch — skipping rerank.")
            return

        scores = self._cross_encoder_svc.score_pairs(job_fp, cand_fps)
        for result, score in zip(results, scores):
            result.rerank_score = score
            c = cand_map.get(result.candidate_id)
            logger.info(
                "[RERANK-CE] %s (%s) → rerank_score=%.4f",
                c.name if c else result.candidate_id,
                result.candidate_id,
                score,
            )

    def _apply_llm_explanations(
        self,
        job: Job,
        results: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        if not results:
            return

        candidates_block = self._build_candidates_block(results, cand_map)
        prompt = self._explanation_prompt.format(
            title=job.title or "",
            normalized_role=job.normalized_role or "",
            seniority_level=job.seniority_level or "not specified",
            experience_min=job.experience_min if job.experience_min is not None else "not specified",
            experience_max=job.experience_max if job.experience_max is not None else "not specified",
            location=job.location or "not specified",
            must_have_skills=", ".join(job.must_have_skills or []),
            good_to_have_skills=", ".join(job.good_to_have_skills or []),
            tools_and_technologies=", ".join(job.tools_and_technologies or []),
            education_requirements=", ".join(job.education_requirements or []),
            certifications=", ".join(job.certifications or []),
            responsibilities="\n  - ".join([""] + (job.responsibilities or [])).lstrip(),
            industry=job.industry or "not specified",
            domain_code=job.domain_code or "not specified",
            subdomain_codes=", ".join(job.subdomain_codes or []),
            summary=job.summary or "",
            candidates_block=candidates_block,
        )

        raw = self._call_explanation_llm(prompt)
        explanation_map = self._parse_explanation_response(raw, results)

        for result in results:
            explanation = explanation_map.get(result.candidate_id)
            if explanation:
                result.explanation = explanation
                logger.info(
                    "[EXPLAIN] %s → %s",
                    result.candidate_id,
                    explanation[:120],
                )

    def _call_explanation_llm(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._settings.rerank_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        usage = response.usage
        if usage:
            logger.info(
                "[EXPLAIN] LLM usage — prompt_tokens: %d  completion_tokens: %d",
                usage.prompt_tokens, usage.completion_tokens,
            )
        return response.choices[0].message.content or "{}"

    def _parse_explanation_response(
        self,
        raw: str,
        results: list[MatchResult],
    ) -> dict[str, str]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("[EXPLAIN] Invalid JSON: %.300s", raw)
            return {}

        if isinstance(parsed, dict):
            for key in ("explanations", "results", "candidates", "rankings"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                if "candidate_id" in parsed and "explanation" in parsed:
                    parsed = [parsed]
                else:
                    parsed = list(parsed.values())[0] if parsed else []

        if not isinstance(parsed, list):
            return {}

        valid_ids = {r.candidate_id for r in results}
        out: dict[str, str] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            cid = item.get("candidate_id")
            expl = item.get("explanation")
            if cid in valid_ids and expl:
                out[cid] = str(expl)
        logger.info("[EXPLAIN] Parsed %d/%d explanations.", len(out), len(results))
        return out

    def _apply_vector_scores(
        self,
        db: Session,
        job: Job,
        passing: list[MatchResult],
        cand_map: dict[str, Candidate],
    ) -> None:
        """Legacy summary-embedding scores — kept for reference."""
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
        if not results:
            return

        job_id = results[0].job_id
        candidate_ids = [r.candidate_id for r in results]
        existing_rows = {
            row.candidate_id: row
            for row in db.query(MatchResult)
            .filter(
                MatchResult.job_id == job_id,
                MatchResult.candidate_id.in_(candidate_ids),
            )
            .all()
        }

        inserted = 0
        updated = 0
        for result in results:
            row = existing_rows.get(result.candidate_id)
            if row is None:
                db.add(result)
                inserted += 1
                continue

            row.is_filtered = result.is_filtered
            row.filter_reason = result.filter_reason
            row.rule_score = result.rule_score
            row.vector_score = result.vector_score
            row.rerank_score = result.rerank_score
            row.llm_score = result.llm_score
            row.final_score = result.final_score
            row.requirement_fit_score = result.requirement_fit_score
            row.requirement_gaps = result.requirement_gaps
            row.explanation = result.explanation
            updated += 1

        db.commit()
        logger.debug(
            "[MATCH] Persisted %d match results — inserted=%d updated=%d.",
            len(results),
            inserted,
            updated,
        )
