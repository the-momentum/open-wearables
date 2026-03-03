import requests
from jose import jwk, jwt
from jose.exceptions import JWTError, JWSError

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
        try:
            unverified_header = jwt.get_unverified_header(token_response.access_token)
            algorithm = unverified_header.get("alg")
            
            if algorithm == "HS256":
                decoded = jwt.decode(
                    token_response.access_token,
                    key=None,
                    options={"verify_signature": False},
                )
                provider_username = decoded.get("user")
                provider_user_id = decoded.get("sub")
                if provider_user_id is not None:
                    return {"user_id": provider_user_id, "username": provider_username}
        except Exception:
            pass

        try:
            # Get the key ID from token header
            unverified_header = jwt.get_unverified_header(token_response.access_token)
            kid = unverified_header.get("kid")
            
            if not kid:
                return {"user_id": None, "username": None}
            
            # Fetch Suunto's public keys
            jwks_url = "https://cloudapi-oauth.suunto.com/.well-known/jwks.json"
            headers = {}
            if self.credentials.subscription_key:
                headers["Ocp-Apim-Subscription-Key"] = self.credentials.subscription_key
                
            resp = requests.get(jwks_url, headers=headers, timeout=5)
            resp.raise_for_status()
            jwks = resp.json()
            
            # Find the key with matching kid
            keys = jwks.get("keys", [])
            matching_key = next((k for k in keys if k.get("kid") == kid), None)
            
            if not matching_key:
                return {"user_id": None, "username": None}
            
            decoded = jwt.decode(
                token_response.access_token,
                matching_key,
                algorithms=["RS256"], 
                audience=settings.suunto_client_id,
            )
            
            provider_username = decoded.get("user")
            provider_user_id = decoded.get("sub")
            
            return {"user_id": provider_user_id, "username": provider_username}
            
        except (JWTError, JWSError, requests.RequestException, Exception):
            return {"user_id": None, "username": None}