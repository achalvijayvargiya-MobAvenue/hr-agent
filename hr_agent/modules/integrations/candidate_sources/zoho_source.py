import logging
import tempfile
import os

from hr_agent.modules.integrations.candidate_sources.base import CandidateSource, CandidateRecord
from hr_agent.modules.integrations.zoho.client import ZohoRecruitClient
from hr_agent.core.services.pdf_service import extract_text

logger = logging.getLogger(__name__)

class ZohoCandidateSource(CandidateSource):
    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory
    @property
    def name(self) -> str:
        return "zoho"

    @property
    def display_name(self) -> str:
        return "Zoho Recruit"

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        """
        Fetch candidates for a specific Job ID.
        Looks up the Job in the database to find its Zoho Job Opening ID.
        """
        if not self._session_factory:
            logger.error("ZohoSource: db_session_factory not configured")
            return []
            
        db = self._session_factory()
        zoho_id = None
        try:
            from hr_agent.modules.jobs.models import Job
            job = db.query(Job).filter_by(id=position_id).first()
            if job and job.zoho_id:
                zoho_id = job.zoho_id
        finally:
            db.close()
            
        if not zoho_id:
            logger.info(f"ZohoSource: Job {position_id} has no zoho_id linked. Skipping Zoho fetch.")
            return []

        client = ZohoRecruitClient()
        records: list[CandidateRecord] = []
        
        logger.info(f"ZohoSource: Fetching applications for Job {position_id} (Zoho ID: {zoho_id})")
        applications = client.get_applications_for_job(zoho_id)
        
        if not applications:
            logger.info(f"No applications found for job {position_id} (Zoho ID: {zoho_id})")
            return []
            
        for app in applications:
            # Get candidate ID from application record
            candidate_id = app.get("$Candidate_Id")
            if not candidate_id:
                continue
                
            logger.info(f"Processing candidate {candidate_id}")
            details = client.get_candidate_details(candidate_id)
            if not details:
                continue
                
            # Check for attachments (CV)
            attachments = client.get_candidate_attachments(candidate_id)
            raw_text = ""
            pdf_bytes = None
            
            if attachments:
                # Get the first attachment (usually the resume)
                att_id = attachments[0].get("id")
                file_name = attachments[0].get("File_Name", "")
                
                if att_id and file_name.lower().endswith(".pdf"):
                    pdf_bytes = client.download_attachment(candidate_id, att_id)
                    if pdf_bytes:
                        try:
                            raw_text = extract_text(pdf_bytes)
                        except Exception as e:
                            logger.error(f"Failed to extract text from {file_name}: {e}")
            
            # Always append the Zoho metadata to the raw text to ensure we don't miss anything
            metadata_text = (
                f"\\n\\n--- ZOHO PROFILE METADATA ---\\n"
                f"Name: {details.get('First_Name', '')} {details.get('Last_Name', '')}\\n"
                f"Email: {details.get('Email', '')}\\n"
                f"Phone: {details.get('Phone', '')} {details.get('Mobile', '')}\\n"
                f"Location: {details.get('City', '')} {details.get('State', '')} {details.get('Country', '')}\\n"
                f"Experience: {details.get('Experience_in_Years', '')}\\n"
                f"Skills: {details.get('Skill_Set', '')}\\n"
                f"Current Title: {details.get('Current_Job_Title', '')}\\n"
                f"Current Employer: {details.get('Current_Employer', '')}\\n"
                f"Expected Salary: {details.get('Expected_Salary', '')}\\n"
                f"Current Salary: {details.get('Current_Salary', '')}\\n"
                f"Educational Details: {details.get('Educational_Details', '')}\\n"
            )
            raw_text = raw_text + metadata_text

            record = CandidateRecord(
                source_name=self.name,
                raw_text=raw_text,
                source_url=f"https://recruit.zoho.in/recruit/EntityInfo.do?module=Candidates&id={candidate_id}",
                name=f"{details.get('First_Name', '')} {details.get('Last_Name', '')}".strip(),
                email=details.get("Email"),
                location=details.get("City") or details.get("Country"),
                metadata={
                    "zoho_candidate_id": candidate_id,
                    "zoho_application_id": app.get("id"),
                    "zoho_job_id": position_id,
                    "status": app.get("Application_Status"),
                    "cv_pdf": pdf_bytes if attachments and pdf_bytes else None
                }
            )
            records.append(record)
            
        return records
