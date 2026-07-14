import logging
import time
import requests
import json
import os
from pydantic import BaseModel
from hr_agent.core.config import get_settings

logger = logging.getLogger(__name__)

CACHE_FILE = ".zoho_token.json"

class ZohoTokenCache(BaseModel):
    access_token: str
    expires_at: float

class ZohoAuthManager:
    # Class-level cache shared across all instances
    _token_cache: ZohoTokenCache | None = None

    def __init__(self):
        self.settings = get_settings()
        self._load_cache_from_file()

    def _load_cache_from_file(self):
        if ZohoAuthManager._token_cache is None and os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    ZohoAuthManager._token_cache = ZohoTokenCache(**data)
                    logger.debug("Loaded Zoho token cache from file.")
            except Exception as e:
                logger.warning(f"Failed to load token cache file: {e}")

    def _save_cache_to_file(self):
        if ZohoAuthManager._token_cache:
            try:
                with open(CACHE_FILE, "w") as f:
                    json.dump(ZohoAuthManager._token_cache.model_dump(), f)
                    logger.debug("Saved Zoho token cache to file.")
            except Exception as e:
                logger.warning(f"Failed to save token cache file: {e}")

    def get_valid_access_token(self) -> str:
        """Returns a valid access token, fetching a new one if necessary."""
        if not self.settings.zoho_client_id or not self.settings.zoho_client_secret or not self.settings.zoho_refresh_token:
            raise ValueError("Zoho credentials (client_id, client_secret, refresh_token) are not fully configured.")

        # Check if we have a valid cached token (with 60s buffer)
        if ZohoAuthManager._token_cache and ZohoAuthManager._token_cache.expires_at > (time.time() + 60):
            return ZohoAuthManager._token_cache.access_token

        return self._refresh_token()

    def _refresh_token(self) -> str:
        """Calls the Zoho OAuth endpoint to get a fresh access token."""
        url = f"https://{self.settings.zoho_dc}/oauth/v2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.settings.zoho_client_id,
            "client_secret": self.settings.zoho_client_secret,
            "refresh_token": self.settings.zoho_refresh_token,
        }
        
        logger.info(f"Refreshing Zoho access token via {url}")
        response = requests.post(url, data=data)
        
        if response.status_code != 200:
            logger.error(f"Failed to refresh Zoho token: {response.text}")
            raise Exception(f"Zoho token refresh failed: {response.status_code} {response.text}")
            
        json_data = response.json()
        if "access_token" not in json_data:
            logger.error(f"Zoho response missing access_token: {json_data}")
            raise Exception(f"Invalid response from Zoho auth: {json_data}")
            
        access_token = json_data["access_token"]
        expires_in = int(json_data.get("expires_in", 3600))
        
        ZohoAuthManager._token_cache = ZohoTokenCache(
            access_token=access_token,
            expires_at=time.time() + expires_in
        )
        self._save_cache_to_file()
        
        return access_token
