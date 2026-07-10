import os

from hr_agent.config import Settings


def test_settings_loads_zoho_credentials_from_project_env_when_cwd_changes(tmp_path, monkeypatch):
    for env_name in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.chdir(tmp_path)
    settings = Settings()

    assert settings.zoho_client_id
    assert settings.zoho_client_secret
    assert settings.zoho_refresh_token
