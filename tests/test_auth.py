"""
Integration tests for the authentication endpoints.

All tests run against an isolated SQLite database via the `client` fixture;
no real Postgres or OpenAI credentials are required.
"""


_REGISTER_URL = "/api/v1/auth/register"
_LOGIN_URL = "/api/v1/auth/login"
_ME_URL = "/api/v1/auth/me"

_USER = {"email": "alice@example.com", "password": "AlicePass123!", "full_name": "Alice"}


def test_register_success(client):
    resp = client.post(_REGISTER_URL, json=_USER)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == _USER["email"]
    assert body["full_name"] == _USER["full_name"]
    assert "id" in body


def test_register_duplicate_email(client):
    client.post(_REGISTER_URL, json=_USER)
    resp = client.post(_REGISTER_URL, json=_USER)
    assert resp.status_code == 409
    assert resp.json()["error"] == "CONFLICT"


def test_login_success(client):
    client.post(_REGISTER_URL, json=_USER)
    resp = client.post(_LOGIN_URL, json={"email": _USER["email"], "password": _USER["password"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert len(body["access_token"]) > 10


def test_login_wrong_password(client):
    client.post(_REGISTER_URL, json=_USER)
    resp = client.post(_LOGIN_URL, json={"email": _USER["email"], "password": "WrongPass!"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


def test_me_authenticated(client, auth_headers):
    resp = client.get(_ME_URL, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "user@test.local"
    assert "id" in body


def test_me_unauthenticated(client):
    resp = client.get(_ME_URL)
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"
