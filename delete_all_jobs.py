from hr_agent.core.database import SessionLocal
from hr_agent.modules.jobs.models import Job
from hr_agent.modules.matching.pool_models import JobCandidatePool

def delete_all_jobs():
    db = SessionLocal()
    try:
        # Delete pools first to avoid foreign key constraint issues if any
        deleted_pools = db.query(JobCandidatePool).delete()
        deleted_jobs = db.query(Job).delete()
        db.commit()
        print(f"Deleted {deleted_pools} pool entries and {deleted_jobs} jobs.")
    except Exception as e:
        db.rollback()
        print(f"Error deleting jobs: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    delete_all_jobs()
