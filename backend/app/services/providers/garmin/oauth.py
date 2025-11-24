import hashlib
import secrets
from base64 import urlsafe_b64encode
from typing import Any

import httpx

from app.config import settings
from app.schemas.oauth import OAuthTokenResponse, ProviderConfig
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class GarminOAuth(BaseOAuthTemplate):
    """Garmin OAuth 2.0 with PKCE implementation."""

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="garmin",
            client_id=settings.garmin_client_id or "",
            client_secret=(
                settings.garmin_client_secret.get_secret_value() if settings.garmin_client_secret else ""
            ),
            redirect_uri=settings.garmin_redirect_uri,
            authorize_url=settings.garmin_authorize_url,
            token_url=settings.garmin_token_url,
            api_base_url=settings.garmin_api_base_url,
            default_scope=settings.garmin_default_scope,
        )

    def _build_auth_url(self, state: str) -> tuple[str, dict[str, Any] | None]:
        """Builds Garmin authorization URL with PKCE."""
        # Generate PKCE pair
        code_verifier = secrets.token_urlsafe(43)
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

        auth_url = (
            f"{self.config.authorize_url}?"
            f"response_type=code&"
            f"client_id={self.config.client_id}&"
            f"code_challenge={code_challenge}&"
            f"code_challenge_method=S256&"
            f"redirect_uri={self.config.redirect_uri}&"
            f"state={state}"
        )

        # Return PKCE data to be saved with state
        pkce_data = {"code_verifier": code_verifier}
        return auth_url, pkce_data

    def _prepare_token_request(self, code: str, code_verifier: str | None) -> tuple[dict, dict]:
        """Prepares Garmin token exchange request (POST body credentials)."""
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code_verifier": code_verifier,
            "redirect_uri": self.config.redirect_uri,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return token_data, headers

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetches Garmin user ID via API."""
        try:
            user_id_response = httpx.get(
                f"{self.config.api_base_url}/wellness-api/rest/user/id",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_id_response.raise_for_status()
            provider_user_id = user_id_response.json().get("userId")
            return {"user_id": provider_user_id, "username": None}
        except Exception:
            return {"user_id": None, "username": None}
