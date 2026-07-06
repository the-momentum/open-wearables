from logging import getLogger

import httpx

from app.config import settings
from app.schemas.auth import (
    AuthenticationMethod,
)
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


class OuraOAuth(BaseOAuthTemplate):
    """Oura Ring OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://cloud.ouraring.com/oauth/authorize",
            token_url="https://api.ouraring.com/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.oura_client_id or "",
            client_secret=(settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else ""),
            redirect_uri=settings.oauth_redirect_uri(ProviderName.OURA),
            default_scope=settings.oura_default_scope,
        )

    # Oura uses body-based auth, no PKCE
    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetch Oura user ID via personal_info endpoint."""
        try:
            response = httpx.get(
                f"{self.api_base_url}/v2/usercollection/personal_info",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            user_data = response.json()
            provider_user_id = user_data.get("id")
            provider_user_id = str(provider_user_id) if provider_user_id is not None else None
            return {"user_id": provider_user_id, "username": None}
        except httpx.HTTPStatusError as e:
            log_structured(
                logger,
                "warning",
                "Oura API error fetching user info",
                action="oura_get_user_info_error",
                status_code=e.response.status_code,
            )
            return {"user_id": None, "username": None}
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            log_structured(
                logger,
                "error",
                "Oura API connection error fetching user info",
                action="oura_connection_error",
                error=str(e),
            )
            return {"user_id": None, "username": None}
