import os
import sys

# Add the project root to the python path so we can import hr_agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hr_agent.services.zoho.client import ZohoRecruitClient
from dotenv import load_dotenv

def test_apps():
    load_dotenv()
    client = ZohoRecruitClient()
    jobs = client.get_active_jobs()
    print(f"Found {len(jobs)} jobs.")
    
    if not jobs:
        print("No jobs found, cannot test apps.")
        return
        
    for job in jobs[:2]:
        job_id = job.get('id')
        job_title = job.get('Posting_Title') or job.get('Job_Opening_Name')
        print(f"\nTesting job {job_id} ({job_title})")
        
        apps = client.get_applications_for_job(job_id)
        print(f"Found {len(apps)} applications.")
        for app in apps:
            print("App:", app)
            
if __name__ == '__main__':
    test_apps()
