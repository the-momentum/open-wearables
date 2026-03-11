from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class DexcomOAuth(BaseOAuthTemplate):
    """Dexcom CGM OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://api.dexcom.com/v2/oauth2/login",
            token_url="https://api.dexcom.com/v2/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.dexcom_client_id or "",
            client_secret=(settings.dexcom_client_secret.get_secret_value() if settings.dexcom_client_secret else ""),
            redirect_uri=settings.dexcom_redirect_uri,
            default_scope=settings.dexcom_default_scope,
        )

    # OAuth configuration — Dexcom expects credentials in request body, no PKCE
    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Dexcom has no user info endpoint — return empty info."""
        return {"user_id": None, "username": None}
