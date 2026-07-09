import logging
import time
import requests
from pydantic import BaseModel
from hr_agent.config import get_settings

logger = logging.getLogger(__name__)

class ZohoTokenCache(BaseModel):
    access_token: str
    expires_at: float

class ZohoAuthManager:
    def __init__(self):
        self.settings = get_settings()
        self._token_cache: ZohoTokenCache | None = None

    def get_valid_access_token(self) -> str:
        """Returns a valid access token, fetching a new one if necessary."""
        if not self.settings.zoho_client_id or not self.settings.zoho_client_secret or not self.settings.zoho_refresh_token:
            raise ValueError("Zoho credentials (client_id, client_secret, refresh_token) are not fully configured.")

        # Check if we have a valid cached token (with 60s buffer)
        if self._token_cache and self._token_cache.expires_at > (time.time() + 60):
            return self._token_cache.access_token

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
        
        self._token_cache = ZohoTokenCache(
            access_token=access_token,
            expires_at=time.time() + expires_in
        )
        
        return access_token
