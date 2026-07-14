import logging
from hr_agent.core.events import bus
from hr_agent.core.database import SessionLocal
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.candidates.models import Candidate
from hr_agent.modules.matching.pool_service import PoolService
from hr_agent.modules.matching.pool_models import JobCandidatePool
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def on_candidate_imported(payload: dict):
    position_id = payload.get('position_id')
    candidate_email = payload.get('candidate_email')
    
    if not position_id or not candidate_email:
        return
        
    logger.info(f"[MatchingModule] Processing CandidateImported event for {candidate_email} on position {position_id}")
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=position_id).first()
        candidate = db.query(Candidate).filter_by(email=candidate_email).first()
        
        if job and candidate:
            existing_pool_entry = db.query(JobCandidatePool).filter_by(job_id=job.id, candidate_id=candidate.email).first()
            if not existing_pool_entry:
                pool_svc = PoolService()
                row = pool_svc._score_candidate(job, candidate, datetime.now(timezone.utc))
                db.add(row)
                db.commit()
                logger.info(f"[MatchingModule] Successfully matched and added {candidate_email} to pool for {position_id}")
    except Exception as e:
        logger.error(f"[MatchingModule] Failed to process CandidateImported event: {e}")
        db.rollback()
    finally:
        db.close()

# Subscribe the listener
bus.subscribe('CandidateImported', on_candidate_imported)
