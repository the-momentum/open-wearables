import logging

import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate

logger = logging.getLogger(__name__)


class GarminOAuth(BaseOAuthTemplate):
    """Garmin OAuth 2.0 with PKCE implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://connect.garmin.com/oauth2Confirm",
            token_url="https://diauth.garmin.com/di-oauth2-service/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.garmin_client_id or "",
            client_secret=(settings.garmin_client_secret.get_secret_value() if settings.garmin_client_secret else ""),
            redirect_uri=settings.garmin_redirect_uri,
            default_scope=settings.garmin_default_scope,
        )

    use_pkce = True
    auth_method = AuthenticationMethod.BODY

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetches Garmin user ID and API permissions."""
        # Fetch user ID (critical - fail returns all None)
        try:
            user_id_response = httpx.get(
                f"{self.api_base_url}/wellness-api/rest/user/id",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_id_response.raise_for_status()
            provider_user_id = user_id_response.json().get("userId")
        except Exception:
            return {"user_id": None, "username": None, "scope": None}

        # Fetch permissions (best-effort - fail returns scope as None)
        scope: str | None = None
        try:
            permissions_response = httpx.get(
                f"{self.api_base_url}/wellness-api/rest/user/permissions",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            permissions_response.raise_for_status()
            data = permissions_response.json()
            # Response format: {"permissions": ["ACTIVITY_EXPORT", "HEALTH_EXPORT", ...]}
            permissions = data.get("permissions", [])
            if permissions:
                scope = " ".join(sorted(permissions))
        except Exception:
            logger.warning(
                "Failed to fetch Garmin permissions for user %s, will retry via webhook",
                provider_user_id,
                exc_info=True,
            )

        return {"user_id": provider_user_id, "username": None, "scope": scope}
