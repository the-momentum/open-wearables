import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class StravaOAuth(BaseOAuthTemplate):
    """Strava OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://www.strava.com/oauth/authorize",
            token_url="https://www.strava.com/api/v3/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.strava_client_id or "",
            client_secret=(settings.strava_client_secret.get_secret_value() if settings.strava_client_secret else ""),
            redirect_uri=settings.strava_redirect_uri,
            default_scope=settings.strava_default_scope,
        )

    # OAuth configuration
    use_pkce: bool = False  # Strava doesn't require PKCE
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY  # Strava expects credentials in body

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetches Strava athlete ID and username via API."""
        try:
            response = httpx.get(
                "https://www.strava.com/api/v3/athlete",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            athlete_data = response.json()
            provider_user_id = athlete_data.get("id")
            provider_user_id = str(provider_user_id) if provider_user_id is not None else None
            username = athlete_data.get("username")
            return {"user_id": provider_user_id, "username": username}
        except Exception:
            return {"user_id": None, "username": None}
