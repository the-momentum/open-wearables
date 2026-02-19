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
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


class WhoopOAuth(BaseOAuthTemplate):
    """Whoop OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://api.prod.whoop.com/oauth/oauth2/auth",
            token_url="https://api.prod.whoop.com/oauth/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.whoop_client_id or "",
            client_secret=(settings.whoop_client_secret.get_secret_value() if settings.whoop_client_secret else ""),
            redirect_uri=settings.whoop_redirect_uri,
            default_scope=settings.whoop_default_scope,
        )

    # OAuth configuration
    use_pkce: bool = False  # Whoop doesn't require PKCE
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY  # Based on Whoop API docs, credentials in body

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetches Whoop user ID via API."""
        try:
            # Whoop API endpoint to get user info
            user_info_response = httpx.get(
                f"{self.api_base_url}/v2/user/profile/basic",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_info_response.raise_for_status()
            user_data = user_info_response.json()
            # Whoop API returns: user_id, email, first_name, last_name
            provider_user_id = user_data.get("user_id")
            provider_user_id = str(provider_user_id) if provider_user_id is not None else None

            log_structured(
                logger,
                "info",
                "Fetched Whoop user profile",
                provider="whoop",
                task="get_provider_user_info",
                user_id=user_id,
            )
            return {"user_id": provider_user_id, "username": None}
        except Exception as e:
            log_structured(
                logger,
                "error",
                f"Failed to fetch Whoop user profile: {e}",
                provider="whoop",
                task="get_provider_user_info",
                user_id=user_id,
            )
            return {"user_id": None, "username": None}
