"""
Integration tests for the position (job) management endpoints.

Covers manual creation, approval workflow, and status-based filtering.
"""


_JOBS_URL = "/api/v1/jobs"


def test_create_manual_position(client, auth_headers):
    resp = client.post(
        f"{_JOBS_URL}/manual",
        json={"title": "Backend Engineer"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Backend Engineer"
    assert body["position_status"] == "DRAFT"
    assert "id" in body


def test_approve_position(client, auth_headers):
    create_resp = client.post(
        f"{_JOBS_URL}/manual",
        json={"title": "Frontend Engineer"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    approve_resp = client.post(
        f"{_JOBS_URL}/{job_id}/approve",
        json={},
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["position_status"] == "OPEN"
    assert body["id"] == job_id


def test_list_positions_by_status(client, auth_headers):
    # Create a DRAFT position (not approved)
    client.post(
        f"{_JOBS_URL}/manual",
        json={"title": "Stays Draft"},
        headers=auth_headers,
    )

    # Create a position and approve it → OPEN
    resp = client.post(
        f"{_JOBS_URL}/manual",
        json={"title": "Goes Open"},
        headers=auth_headers,
    )
    job_id = resp.json()["id"]
    client.post(f"{_JOBS_URL}/{job_id}/approve", json={}, headers=auth_headers)

    # Query only OPEN positions
    list_resp = client.get(f"{_JOBS_URL}?status=OPEN", headers=auth_headers)
    assert list_resp.status_code == 200
    results = list_resp.json()

    assert len(results) >= 1
    assert all(r["position_status"] == "OPEN" for r in results)
    assert any(r["title"] == "Goes Open" for r in results)
    assert not any(r["title"] == "Stays Draft" for r in results)
