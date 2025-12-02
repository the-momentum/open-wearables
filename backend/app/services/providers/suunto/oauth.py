from jose import jwt

from app.config import settings
from app.schemas import OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class SuuntoOAuth(BaseOAuthTemplate):
    """Suunto OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://cloudapi-oauth.suunto.com/oauth/authorize",
            token_url="https://cloudapi-oauth.suunto.com/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.suunto_client_id or "",
            client_secret=(settings.suunto_client_secret.get_secret_value() if settings.suunto_client_secret else ""),
            redirect_uri=settings.suunto_redirect_uri,
            default_scope=settings.suunto_default_scope,
            subscription_key=(
                settings.suunto_subscription_key.get_secret_value() if settings.suunto_subscription_key else ""
            ),
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts Suunto user info from JWT access token."""
        try:
            # jwt.decode requires a key parameter, but we're not verifying signature
            decoded = jwt.decode(
                token_response.access_token,
                key="",  # Empty key since we're not verifying
                options={"verify_signature": False},
            )
            provider_username = decoded.get("user")
            provider_user_id = decoded.get("sub")
            return {"user_id": provider_user_id, "username": provider_username}
        except Exception:
            return {"user_id": None, "username": None}
