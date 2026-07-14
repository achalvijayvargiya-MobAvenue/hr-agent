"""Tests for match result persistence (upsert behaviour)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hr_agent.core.database import Base
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.matching.models import MatchResult
from hr_agent.modules.matching.service import MatchingService


def test_persist_upserts_existing_row():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    job = Job(id="job-1", title="Test Role", normalized_role="test_role")
    candidate = Candidate(email="a@test.com", name="Alice", normalized_role="test_role")
    db.add_all([job, candidate])
    db.add(
        MatchResult(
            job_id="job-1",
            candidate_id="a@test.com",
            is_filtered=False,
            final_score=0.5,
            vector_score=0.4,
        )
    )
    db.commit()

    updated = MatchResult(
        job_id="job-1",
        candidate_id="a@test.com",
        is_filtered=False,
        final_score=0.9,
        vector_score=0.8,
        rerank_score=0.95,
        explanation="Strong fit.",
    )
    MatchingService._persist(db, [updated])

    rows = db.query(MatchResult).filter_by(job_id="job-1").all()
    assert len(rows) == 1
    assert rows[0].final_score == 0.9
    assert rows[0].vector_score == 0.8
    assert rows[0].rerank_score == 0.95
    assert rows[0].explanation == "Strong fit."

    db.close()
