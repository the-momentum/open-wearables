import requests
from jose import jwk, jwt

from app.config import settings
from app.schemas import OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import handle_exceptions


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

    @handle_exceptions
    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts and verifies Suunto user info from JWT access token."""
        # Get unverified header to locate the key id (kid)
        unverified_header = jwt.get_unverified_header(token_response.access_token)
        kid = unverified_header.get("kid")

        jwks_url = "https://cloudapi-oauth.suunto.com/.well-known/jwks.json"
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        jwks = resp.json()
        keys = jwks.get("keys", [])
        matching = next((k for k in keys if k.get("kid") == kid), None)
        if not matching:
            raise ValueError("No matching JWK found for token kid")

        # Construct a key object and obtain a PEM representation for decoding
        public_key = jwk.construct(matching)
        try:
            public_pem = public_key.to_pem()
        except Exception:
            # Fallback: if to_pem is not available, pass the jwk dict directly
            public_pem = matching

        decoded = jwt.decode(
            token_response.access_token,
            public_pem,
            algorithms=["RS256"],
            audience=settings.suunto_client_id,
        )

        provider_username = decoded.get("user")
        provider_user_id = decoded.get("sub")
        return {"user_id": provider_user_id, "username": provider_username}
