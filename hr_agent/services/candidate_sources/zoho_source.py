import logging
import tempfile
import os

from hr_agent.services.candidate_sources.base import CandidateSource, CandidateRecord
from hr_agent.services.zoho.client import ZohoRecruitClient
from hr_agent.services.pdf_service import extract_text

logger = logging.getLogger(__name__)

class ZohoCandidateSource(CandidateSource):
    @property
    def name(self) -> str:
        return "zoho"

    @property
    def display_name(self) -> str:
        return "Zoho Recruit"

    def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
        """
        Fetch candidates for a specific Zoho Job Opening ID.
        position_id here is expected to be the Zoho Job Opening ID.
        """
        client = ZohoRecruitClient()
        records: list[CandidateRecord] = []
        
        logger.info(f"ZohoSource: Fetching applications for Job {position_id}")
        applications = client.get_applications_for_job(position_id)
        
        if not applications:
            logger.info(f"No applications found for job {position_id}")
            return []
            
        for app in applications:
            # The application record usually links to a Candidate
            candidate_dict = app.get("Candidate")
            if not candidate_dict:
                continue
                
            candidate_id = candidate_dict.get("id")
            if not candidate_id:
                continue
                
            logger.info(f"Processing candidate {candidate_id}")
            details = client.get_candidate_details(candidate_id)
            if not details:
                continue
                
            # Check for attachments (CV)
            attachments = client.get_candidate_attachments(candidate_id)
            raw_text = ""
            
            if attachments:
                # Get the first attachment (usually the resume)
                att_id = attachments[0].get("id")
                file_name = attachments[0].get("File_Name", "")
                
                if att_id and file_name.lower().endswith(".pdf"):
                    pdf_bytes = client.download_attachment(candidate_id, att_id)
                    if pdf_bytes:
                        # Write to temp file to use pdf_service
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(pdf_bytes)
                            tmp_path = tmp.name
                            
                        try:
                            raw_text = extract_text(tmp_path)
                        except Exception as e:
                            logger.error(f"Failed to extract text from {file_name}: {e}")
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
            
            # Fallback to plain text details if no PDF text extracted
            if len(raw_text.strip()) < 50:
                logger.info(f"Using fallback text for candidate {candidate_id}")
                raw_text = (
                    f"Name: {details.get('First_Name', '')} {details.get('Last_Name', '')}\n"
                    f"Email: {details.get('Email', '')}\n"
                    f"Experience: {details.get('Experience_in_Years', '')}\n"
                    f"Skills: {details.get('Skill_Set', '')}\n"
                    f"Current Title: {details.get('Current_Job_Title', '')}\n"
                    f"Current Employer: {details.get('Current_Employer', '')}\n"
                )

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
                    "status": app.get("Application_Status")
                }
            )
            records.append(record)
            
        return records
