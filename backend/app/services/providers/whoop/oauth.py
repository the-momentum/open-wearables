import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


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
                f"{self.api_base_url}/developer/v2/user/profile/basic",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_info_response.raise_for_status()
            user_data = user_info_response.json()
            # Adjust based on actual Whoop API response structure
            provider_user_id = user_data.get("user_id") or user_data.get("id")
            username = user_data.get("username") or user_data.get("email")
            return {"user_id": str(provider_user_id) if provider_user_id else None, "username": username}
        except Exception:
            # If user info fetch fails, connection can still be saved without provider_user_id
            return {"user_id": None, "username": None}
