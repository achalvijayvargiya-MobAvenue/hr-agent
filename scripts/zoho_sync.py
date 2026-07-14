import logging
import asyncio
import sys
import os
import re
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
            # Normalize Employment Type
            employment_type = z_job.get("Job_Type")
            if employment_type:
                # Zoho often uses "Full time" instead of "Full-time"
                emp_lower = employment_type.lower().replace("-", " ")
                if emp_lower == "full time":
                    employment_type = "Full-time"
                elif emp_lower == "part time":
                    employment_type = "Part-time"
            
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
            if experience_str:
                nums = re.findall(r'\d+', experience_str)
                if len(nums) >= 2:
                    exp_min = int(nums[0])
                    exp_max = int(nums[1])
                elif len(nums) == 1:
                    exp_min = int(nums[0])
                    
            # Extract Candidates Required
            candidates_required = None
            num_positions = z_job.get("Number_of_Positions")
            if num_positions:
                try:
                    candidates_required = int(num_positions)
                except ValueError:
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
                    candidates_required=candidates_required,
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
                if candidates_required is not None: db_job.candidates_required = candidates_required
                db_job.position_status = "OPEN"
                
            db.commit()
            
            # Fetch candidates for this job
            z_short_id = str(z_job.get("Job_Opening_ID"))
            if z_short_id and z_short_id != "None":
                records = zoho_source.fetch(z_short_id)
                for record in records:
                    c_id = str(record.metadata.get("zoho_candidate_id"))
                    # Candidate model uses email as primary key
                    email = record.email or f"{c_id}@zoho.local"
                    
                    db_candidate = db.query(Candidate).filter(Candidate.email == email).first()
                    cv_pdf_data = record.metadata.get("cv_pdf")
                    if not db_candidate:
                        logger.info(f"Adding new candidate: {record.name}")
                        db_candidate = Candidate(
                            email=email,
                            name=record.name or "Unknown",
                            raw_text=record.raw_text,
                            cv_pdf=cv_pdf_data,
                            source_name="zoho",
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(db_candidate)
                        
                        # Process extraction and embedding immediately so UI shows data
                        try:
                            from hr_agent.api.deps import get_extraction_service, get_embedding_service
                            from hr_agent.services.candidate_service import apply_extraction_to_candidate
                            from hr_agent.services.profile_fingerprint_service import build_candidate_fingerprint
                            from hr_agent.models.processing_log import ProcessingLog, ProcessingStatus
                            
                            ex_svc = get_extraction_service()
                            em_svc = get_embedding_service()
                            
                            extracted = ex_svc.extract_cv(record.raw_text)
                            apply_extraction_to_candidate(db_candidate, extracted)
                            
                            # Also generate embeddings
                            em_svc.generate_and_store(db, "candidate", email, extracted.summary)
                            em_svc.ensure_fingerprint_embedding(
                                db, "candidate", email, build_candidate_fingerprint(db_candidate)
                            )
                            
                            # Create a COMPLETED ProcessingLog so it doesn't show PENDING
                            log = ProcessingLog(
                                entity_id=email,
                                entity_type="candidate",
                                status=ProcessingStatus.EMBEDDED
                            )
                            db.add(log)
                        except Exception as e:
                            logger.error(f"Failed to process candidate {email}: {e}")

                    else:
                        if cv_pdf_data and not db_candidate.cv_pdf:
                            db_candidate.cv_pdf = cv_pdf_data
                    
                    # Ensure candidate is in the pool for this job
                    from hr_agent.models.job_candidate_pool import JobCandidatePool
                    db_pool = db.query(JobCandidatePool).filter_by(job_id=db_job.id, candidate_id=email).first()
                    if not db_pool:
                        db_pool = JobCandidatePool(
                            job_id=db_job.id,
                            candidate_id=email,
                            pool_status="in_pool"
                        )
                        db.add(db_pool)
                
                db.commit()
            else:
                logger.warning(f"Could not fetch candidates for {title}, missing Job_Opening_ID")
            
        logger.info("Zoho Sync completed successfully.")
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(sync_zoho())
