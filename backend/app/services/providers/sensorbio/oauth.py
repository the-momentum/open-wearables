import logging
from typing import Any

import httpx

from app.config import settings
from app.schemas.auth import AuthenticationMethod
from app.schemas.model_crud.credentials import OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


class SensorBioOAuth(BaseOAuthTemplate):
    """Sensor Bio OAuth 2.0 implementation."""

    use_pkce = False
    auth_method = AuthenticationMethod.BODY

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://auth.sensorbio.com/authorize",
            token_url="https://auth.sensorbio.com/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.sensorbio_client_id or "",
            client_secret=(
                settings.sensorbio_client_secret.get_secret_value() if settings.sensorbio_client_secret else ""
            ),
            redirect_uri=f"{settings.api_base_url}/api/v1/oauth/callback/sensorbio",
            default_scope=settings.sensorbio_default_scope,
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, Any]:
        """Fetches Sensor Bio user profile via /v1/user."""
        try:
            response = httpx.get(
                f"{self.api_base_url}/v1/user",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else {}

            log_structured(
                logger,
                "info",
                "Fetched Sensor Bio user profile",
                provider="sensorbio",
                task="get_provider_user_info",
                user_id=user_id,
            )
            return {
                "user_id": str(data.get("id")) if data.get("id") is not None else None,
                "username": data.get("name"),
            }
        except httpx.HTTPStatusError as e:
            log_structured(
                logger,
                "warning",
                "Sensor Bio API HTTP error fetching user profile",
                provider="sensorbio",
                task="get_provider_user_info",
                user_id=user_id,
                status_code=e.response.status_code,
            )
            return {"user_id": None, "username": None}
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            log_structured(
                logger,
                "error",
                "Sensor Bio API connection error fetching user profile",
                provider="sensorbio",
                task="get_provider_user_info",
                user_id=user_id,
                error=str(e),
            )
            return {"user_id": None, "username": None}
        except Exception as e:
            log_structured(
                logger,
                "error",
                f"Unexpected error fetching Sensor Bio user profile: {e}",
                provider="sensorbio",
                task="get_provider_user_info",
                user_id=user_id,
            )
            return {"user_id": None, "username": None}
