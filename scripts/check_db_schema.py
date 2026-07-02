"""Quick schema check — run: python scripts/check_db_schema.py"""
from sqlalchemy import create_engine, inspect, text

from hr_agent.config import get_settings
from hr_agent.database import SessionLocal
from hr_agent.models.job import Job

settings = get_settings()
print(f"Database: {settings.database_url.split('@')[-1]}")

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"Alembic version: {version}")

insp = inspect(engine)
job_cols = {c["name"] for c in insp.get_columns("jobs")}
required = {
    "domain_code",
    "domain_label",
    "subdomain_codes",
    "requirement_fit_score",  # on match_results
}
missing_jobs = [c for c in required if c in {"domain_code", "domain_label", "subdomain_codes"} and c not in job_cols]
print(f"Missing job columns: {missing_jobs or 'none'}")

match_cols = {c["name"] for c in insp.get_columns("match_results")}
if "rerank_score" not in match_cols:
    print("Missing match_results.rerank_score")
else:
    print("match_results.rerank_score: OK")

db = SessionLocal()
try:
    count = db.query(Job).count()
    print(f"ORM query OK — {count} jobs")
finally:
    db.close()
