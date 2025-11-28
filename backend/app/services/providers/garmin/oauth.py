import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


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
        """Fetches Garmin user ID via API."""
        try:
            user_id_response = httpx.get(
                f"{self.api_base_url}/wellness-api/rest/user/id",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            user_id_response.raise_for_status()
            provider_user_id = user_id_response.json().get("userId")
            return {"user_id": provider_user_id, "username": None}
        except Exception:
            return {"user_id": None, "username": None}
