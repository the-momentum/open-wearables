from jose import jwt
from jose.exceptions import JWTError

from app.config import settings
from app.schemas.model_crud.credentials import (
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
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
        """Extracts and verifies Suunto user info from JWT access token."""
        credentials = self.credentials
        if not credentials.client_secret or not credentials.client_id:
            return {"user_id": None, "username": None}
        try:
            decoded = jwt.decode(
                token_response.access_token,
                credentials.client_secret,
                algorithms=["HS256"],
                audience=credentials.client_id,
            )

            if not decoded.get("sub"):
                raise ValueError("JWT signature verification failed")

            return {
                "user_id": decoded.get("sub"),
                "username": decoded.get("user"),
            }

        except JWTError:
            raise ValueError("JWT signature verification failed")
