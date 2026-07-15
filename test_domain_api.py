import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Get a job ID
        resp = await client.get("http://127.0.0.1:8000/api/v1/jobs")
        jobs = resp.json()
        if not jobs:
            print("No jobs found")
            return
        
        job_id = jobs[0]["id"]
        print(f"Job ID: {job_id}")
        
        # Try to update domain
        domain_body = {
            "domain_code": "TECH",
            "subdomain_codes": ["TECH.SWE.BACKEND"]
        }
        resp = await client.put(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/domain", json=domain_body)
        print("Update Domain Status:", resp.status_code)
        print("Update Domain Response:", resp.text)
        
        # Build pool
        resp = await client.post(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/pool/build")
        print("Build Pool Status:", resp.status_code)
        print("Build Pool Response:", resp.text)

asyncio.run(main())
