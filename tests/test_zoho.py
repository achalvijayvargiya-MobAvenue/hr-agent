"""Unit tests for Zoho OAuth and API client."""
from unittest.mock import MagicMock, patch

import pytest

from hr_agent.config import Settings
from hr_agent.services.candidate_sources.zoho.auth import ZohoAuthError, ZohoAuthManager
from hr_agent.services.candidate_sources.zoho.client import ZohoClient
from hr_agent.services.candidate_sources.zoho.candidate_service import (
    extract_email,
    extract_full_name,
    profile_to_raw_text,
    upsert_zoho_candidate,
)


@pytest.fixture
def zoho_settings():
    return Settings(
        zoho_client_id="test-client-id",
        zoho_client_secret="test-client-secret",
        zoho_refresh_token="test-refresh-token",
        zoho_accounts_url="https://accounts.zoho.com",
        zoho_recruit_api_url="https://recruit.zoho.com/recruit/v2",
    )


def test_auth_manager_demo_mode():
    settings = Settings(zoho_demo_mode=True)
    auth = ZohoAuthManager(settings)
    assert auth.is_configured()
    assert auth.get_access_token() == "demo-token"


def test_auth_manager_not_configured(zoho_settings):
    incomplete = Settings()
    auth = ZohoAuthManager(incomplete)
    assert not auth.is_configured()
    with pytest.raises(ZohoAuthError):
        auth.get_access_token()


@patch("hr_agent.services.candidate_sources.zoho.auth.requests.post")
def test_auth_manager_refresh(mock_post, zoho_settings):
    mock_post.return_value = MagicMock(
        ok=True,
        json=lambda: {"access_token": "fresh-token", "expires_in": 3600},
    )
    auth = ZohoAuthManager(zoho_settings)
    token = auth.get_access_token()
    assert token == "fresh-token"
    token2 = auth.get_access_token()
    assert token2 == "fresh-token"
    mock_post.assert_called_once()


def test_client_health_demo_mode():
    settings = Settings(zoho_demo_mode=True)
    client = ZohoClient(settings)
    result = client.health_check()
    assert result["ok"] is True
    assert result["demo_mode"] is True


def test_profile_to_raw_text():
    record = {
        "Full_Name": "Jane Doe",
        "Email": "jane@example.com",
        "Current_Job_Title": "Engineer",
        "Skill_Set": "Python",
    }
    text = profile_to_raw_text(record)
    assert "Jane Doe" in text
    assert "jane@example.com" in text
    assert "Python" in text


def test_extract_email_normalizes():
    assert extract_email({"Email": "  Test@Example.COM  "}) == "test@example.com"


def test_extract_full_name_composes():
    assert extract_full_name({"First_Name": "Jane", "Last_Name": "Doe"}) == "Jane Doe"


def test_upsert_zoho_candidate(db_session):
    record = {
        "id": "999001",
        "Full_Name": "Sync Test",
        "Email": "sync.test@example.com",
        "Modified_Time": "2026-07-01T00:00:00+05:30",
    }
    row = upsert_zoho_candidate(db_session, record)
    db_session.commit()
    assert row is not None
    assert row.zoho_id == "999001"
    assert row.email == "sync.test@example.com"
    assert row.full_name == "Sync Test"
