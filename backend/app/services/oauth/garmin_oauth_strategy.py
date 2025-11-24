"""Garmin OAuth 2.0 with PKCE strategy."""

import hashlib
import secrets
from base64 import urlsafe_b64encode

import httpx

from app.schemas import OAuthTokenResponse, ProviderConfig

from .base_oauth_strategy import BaseOAuthStrategy


class GarminOAuthStrategy(BaseOAuthStrategy):
    """Garmin OAuth 2.0 with PKCE implementation."""

    def requires_pkce(self) -> bool:
        """Garmin requires PKCE."""
        return True

    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge pair.

        Returns:
            tuple: (code_verifier, code_challenge)
        """
        # Generate code_verifier: random string 43-128 characters
        code_verifier = secrets.token_urlsafe(43)

        # Generate code_challenge: SHA-256 hash of code_verifier, base64url encoded
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

        return code_verifier, code_challenge

    def build_authorization_url(
        self,
        config: ProviderConfig,
        state: str,
    ) -> tuple[str, dict | None]:
        """Build Garmin authorization URL with PKCE."""
        # Generate PKCE pair
        code_verifier, code_challenge = self.generate_pkce_pair()

        auth_url = (
            f"{config.authorize_url}?"
            f"response_type=code&"
            f"client_id={config.client_id}&"
            f"code_challenge={code_challenge}&"
            f"code_challenge_method=S256&"
            f"redirect_uri={config.redirect_uri}&"
            f"state={state}"
        )

        # Return PKCE data to be saved with state
        pkce_data = {"code_verifier": code_verifier}
        return auth_url, pkce_data

    def prepare_token_exchange(
        self,
        config: ProviderConfig,
        code: str,
        code_verifier: str | None = None,
    ) -> tuple[dict, dict]:
        """Prepare Garmin token exchange request.

        Garmin sends credentials in POST body, not as Basic Auth.
        """
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code_verifier": code_verifier,
            "redirect_uri": config.redirect_uri,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return token_data, headers

    def prepare_token_refresh(
        self,
        config: ProviderConfig,
        refresh_token: str,
    ) -> tuple[dict, dict]:
        """Prepare Garmin token refresh request."""
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return refresh_data, headers

    def extract_provider_user_info(
        self,
        config: ProviderConfig,
        token_response: OAuthTokenResponse,
        user_id: str,
    ) -> dict[str, str | None]:
        """Fetch Garmin user ID via API."""
        try:
            user_id_response = httpx.get(
                f"{config.api_base_url}/wellness-api/rest/user/id",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_id_response.raise_for_status()
            provider_user_id = user_id_response.json().get("userId")
            return {"user_id": provider_user_id, "username": None}
        except Exception:
            return {"user_id": None, "username": None}
