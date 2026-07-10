import asyncio
from hr_agent.services.zoho.client import ZohoRecruitClient

async def test_zoho_candidates():
    client = ZohoRecruitClient()
    url = f"{client.base_url}/Candidates"
    headers = client._get_headers()
    response = client.session.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        candidates = data.get("data", [])
        print(f"Found {len(candidates)} candidates.")
        if candidates:
            print("Sample candidate:", candidates[0])
    else:
        print(f"Error: {response.status_code} {response.text}")

if __name__ == "__main__":
    asyncio.run(test_zoho_candidates())
