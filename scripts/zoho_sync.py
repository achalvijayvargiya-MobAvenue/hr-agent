import logging
import asyncio
import sys
import os
from datetime import datetime, timezone

# Add the project root to the Python path so we can import hr_agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hr_agent.database import SessionLocal
from hr_agent.models.job import Job
from hr_agent.models.candidate import Candidate
from hr_agent.services.zoho.client import ZohoRecruitClient
from hr_agent.api.deps import get_source_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def sync_zoho():
    logger.info("Starting Zoho Sync...")
    
    try:
        client = ZohoRecruitClient()
        zoho_jobs = client.get_active_jobs()
    except Exception as e:
        logger.error(f"Failed to fetch jobs from Zoho. Have you configured the refresh token? Error: {e}")
        return

    db = SessionLocal()
    registry = get_source_registry()
    zoho_source = registry.get("zoho")
    
    if not zoho_source:
        logger.error("Zoho source is not registered.")
        return

    try:
        for z_job in zoho_jobs:
            z_job_id = str(z_job.get("id"))
            title = z_job.get("Job_Opening_Name")
            desc = z_job.get("Job_Description") or "No description provided."
            
            if not z_job_id or not title:
                continue
                
            # Upsert Job
            db_job = db.query(Job).filter(Job.id == z_job_id).first()
            if not db_job:
                logger.info(f"Creating new Job from Zoho: {title}")
                
                # Combine description and requirements for raw_text
                reqs = z_job.get("Required_Skills", "")
                full_text = f"{desc}\n\nRequirements:\n{reqs}"
                
                db_job = Job(
                    id=z_job_id,
                    title=title,
                    summary=desc,
                    raw_text=full_text,
                    position_status="OPEN",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(db_job)
                db.commit()
            
            # Fetch candidates for this job
            records = zoho_source.fetch(z_job_id)
            for record in records:
                c_id = str(record.metadata.get("zoho_candidate_id"))
                # Candidate model uses email as primary key
                email = record.email or f"{c_id}@zoho.local"
                
                db_candidate = db.query(Candidate).filter(Candidate.email == email).first()
                if not db_candidate:
                    logger.info(f"Adding new candidate: {record.name}")
                    db_candidate = Candidate(
                        email=email,
                        name=record.name or "Unknown",
                        raw_text=record.raw_text,
                        source_name="zoho",
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(db_candidate)
            
            db.commit()
            
        logger.info("Zoho Sync completed successfully.")
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(sync_zoho())
