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
            title = z_job.get("Job_Opening_Name", "Unknown Title")
            desc = z_job.get("Job_Description", "")
            
            # Extract new fields
            industry = z_job.get("Industry", "")
            
            department_raw = z_job.get("Department_Name", "")
            if isinstance(department_raw, dict):
                department = department_raw.get("name", "")
            else:
                department = str(department_raw) if department_raw else ""
                
            employment_type = z_job.get("Job_Type", "")
            
            # Combine location
            city = z_job.get("City", "")
            state = z_job.get("State", "")
            country = z_job.get("Country", "")
            location_parts = [p for p in [city, state, country] if p]
            location = ", ".join(location_parts) if location_parts else None

            # Parse work experience
            experience_str = str(z_job.get("Work_Experience", ""))
            exp_min = None
            exp_max = None
            if experience_str and "-" in experience_str:
                parts = experience_str.split("-")
                try:
                    exp_min = int(parts[0].strip().split()[0])
                    exp_max = int(parts[1].strip().split()[0])
                except Exception:
                    pass
            elif experience_str:
                try:
                    exp_min = int(experience_str.strip().split()[0])
                except Exception:
                    pass
            
            # Combine description and requirements for raw_text
            reqs = z_job.get("Required_Skills", "")
            full_text = f"{desc}\n\nRequirements:\n{reqs}"
            
            # Upsert Job (Check by ID or Title to prevent duplicates)
            db_job = db.query(Job).filter((Job.id == z_job_id) | (Job.title == title)).first()
            if not db_job:
                logger.info(f"Creating new Job from Zoho: {title}")
                db_job = Job(
                    id=z_job_id,
                    title=title,
                    summary=desc,
                    raw_text=full_text,
                    industry=industry,
                    department=department,
                    employment_type=employment_type,
                    location=location,
                    experience_min=exp_min,
                    experience_max=exp_max,
                    position_status="OPEN",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(db_job)
            else:
                logger.info(f"Updating existing Job: {title}")
                db_job.summary = desc
                db_job.raw_text = full_text
                if industry: db_job.industry = industry
                if department: db_job.department = department
                if employment_type: db_job.employment_type = employment_type
                if location: db_job.location = location
                if exp_min is not None: db_job.experience_min = exp_min
                if exp_max is not None: db_job.experience_max = exp_max
                db_job.position_status = "OPEN"
                
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
