"""
Smoke test -- verifies the HR Agent API is reachable and behaves correctly
against PostgreSQL.

Run with:
    python scripts/smoke_test.py

Exits with code 0 if all checks pass, 1 if any fail.
Requires the server to be running: uvicorn hr_agent.main:app --reload
"""
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"
API_V1 = f"{BASE_URL}/api/v1"

results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    results.append((name, passed, detail))


# --- Check 1: GET /health ---
print("\n--- Check 1: GET /health")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    check('body {"status":"ok"}', r.json() == {"status": "ok"}, f"got {r.text}")
except Exception as exc:
    check("GET /health reachable", False, str(exc))
    check('body {"status":"ok"}', False, "skipped")

# --- Check 2: POST /api/v1/jobs/upload with no auth -> 401 ---
print("\n--- Check 2: POST /api/v1/jobs/upload (no auth -> 401 Unauthorized)")
try:
    r = requests.post(f"{API_V1}/jobs/upload", timeout=5)
    check("status 401", r.status_code == 401, f"got {r.status_code}")
except Exception as exc:
    check("POST /api/v1/jobs/upload reachable", False, str(exc))

# --- Check 3: GET /api/v1/matches/<nonexistent-id> -> 401 (auth required) ---
print("\n--- Check 3: GET /api/v1/matches/nonexistent-id (expect 401 — auth required)")
try:
    r = requests.get(f"{API_V1}/matches/nonexistent-id", timeout=5)
    check(
        "status 401",
        r.status_code == 401,
        f"got {r.status_code}",
    )
except Exception as exc:
    check("GET /api/v1/matches/nonexistent-id reachable", False, str(exc))

# --- Summary ---
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n--- Summary: {passed}/{total} passed", end="")
if failed:
    print(f", {failed} FAILED")
    sys.exit(1)
else:
    print(" OK")
    sys.exit(0)
