"""
Central configuration — all tuneable values live here.
Override any value via environment variable or a .env file.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoreWeights(BaseSettings):
    """Weights applied at the final score combination stage."""

    rule: float = 0.4
    vector: float = 0.2
    llm: float = 0.4

    @model_validator(mode="after")
    def must_sum_to_one(self) -> "ScoreWeights":
        total = self.rule + self.vector + self.llm
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"score weights must sum to 1.0, got {total:.4f}")
        return self


class RuleSubWeights(BaseSettings):
    """Weights for the four components inside the rule score."""

    skill: float = 0.4
    experience: float = 0.2
    role: float = 0.2
    industry: float = 0.2

    @model_validator(mode="after")
    def must_sum_to_one(self) -> "RuleSubWeights":
        total = self.skill + self.experience + self.role + self.industry
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"rule sub-weights must sum to 1.0, got {total:.4f}")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"           # DEBUG | INFO | WARNING | ERROR
    log_file: str = "logs/hr_agent.log"
    log_backup_days: int = 30         # daily rotated files to retain

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./hr_agent.db"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    extraction_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    rerank_model: str = "gpt-4o"

    # ── Extraction ────────────────────────────────────────────────────────────
    max_extraction_retries: int = 2

    # ── Matching ──────────────────────────────────────────────────────────────
    top_n_for_rerank: int = 20

    # ── Final score weights ───────────────────────────────────────────────────
    rule_weight: float = 0.4
    vector_weight: float = 0.2
    llm_weight: float = 0.4

    # ── Rule sub-weights ──────────────────────────────────────────────────────
    skill_weight: float = 0.4
    experience_weight: float = 0.2
    role_weight: float = 0.2
    industry_weight: float = 0.2

    # ── GitHub candidate source ─────────────────────────────────────────────────
    github_token: str = ""
    github_max_results: int = 30
    github_enrich_profiles: bool = True
    github_demo_mode: bool = False

    # ── Security / JWT ────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @property
    def score_weights(self) -> ScoreWeights:
        return ScoreWeights(
            rule=self.rule_weight,
            vector=self.vector_weight,
            llm=self.llm_weight,
        )

    @property
    def rule_sub_weights(self) -> RuleSubWeights:
        return RuleSubWeights(
            skill=self.skill_weight,
            experience=self.experience_weight,
            role=self.role_weight,
            industry=self.industry_weight,
        )


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance (loaded once, cached for the process lifetime)."""
    return Settings()
