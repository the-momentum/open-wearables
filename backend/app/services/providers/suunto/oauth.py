import jwt

from app.config import settings
from app.schemas.oauth import OAuthTokenResponse, ProviderConfig
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class SuuntoOAuth(BaseOAuthTemplate):
    """Suunto OAuth 2.0 implementation."""

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="suunto",
            client_id=settings.suunto_client_id or "",
            client_secret=(
                settings.suunto_client_secret.get_secret_value() if settings.suunto_client_secret else ""
            ),
            redirect_uri=settings.suunto_redirect_uri,
            authorize_url=settings.suunto_authorize_url,
            token_url=settings.suunto_token_url,
            api_base_url=settings.suunto_api_base_url,
            default_scope=settings.suunto_default_scope,
            subscription_key=(
                settings.suunto_subscription_key.get_secret_value() if settings.suunto_subscription_key else ""
            ),
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts Suunto user info from JWT access token."""
        try:
            decoded = jwt.decode(token_response.access_token, options={"verify_signature": False})
            provider_username = decoded.get("user")
            provider_user_id = decoded.get("sub")
            return {"user_id": provider_user_id, "username": provider_username}
        except Exception:
            return {"user_id": None, "username": None}
