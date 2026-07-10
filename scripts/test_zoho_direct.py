import os
import sys

# Add the project root to the python path so we can import hr_agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from hr_agent.main import app
from hr_agent.database import get_db

def test_endpoints():
    client = TestClient(app)
    # We need to bypass auth, but wait, the endpoint is protected by Depends(get_current_user).
    # Since we are just testing Zoho client directly, let's just use ZohoRecruitClient.
    from hr_agent.services.zoho.client import ZohoRecruitClient
    zoho_client = ZohoRecruitClient()
    
    # We use one of the job IDs from the user's log
    job_id = "86740000001535096"
    print(f"Testing URLs for job {job_id}")

    urls = [
        f"{zoho_client.base_url}/Job_Openings/{job_id}/Candidates",
        f"{zoho_client.base_url}/JobOpenings/{job_id}/Candidates",
        f"{zoho_client.base_url}/Applications/search?criteria=(Job_Opening_ID:equals:{job_id})",
        f"{zoho_client.base_url}/Applications/search?criteria=(Job_Opening_Id:equals:{job_id})",
        f"{zoho_client.base_url}/Candidates/search?criteria=(Job_Opening_ID:equals:{job_id})"
    ]

    for url in urls:
        print(f"\n--- Testing: {url} ---")
        try:
            r = zoho_client.session.get(url, headers=zoho_client._get_headers())
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:300]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    test_endpoints()
