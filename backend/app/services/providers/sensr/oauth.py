from typing import Any

import httpx
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from app.config import settings
from app.schemas.oauth import AuthenticationMethod, OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured


class SensrOAuth(BaseOAuthTemplate):
    """Sensr OAuth 2.0 implementation."""

    use_pkce = False
    auth_method = AuthenticationMethod.BODY

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://auth.getsensr.io/authorize",
            token_url="https://auth.getsensr.io/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.sensr_client_id or "",
            client_secret=settings.sensr_client_secret.get_secret_value() if settings.sensr_client_secret else "",
            redirect_uri=settings.sensr_redirect_uri,
            default_scope=settings.sensr_default_scope,
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self.api_base_url}/v1/user",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            return {
                "user_id": str(data.get("id")) if data.get("id") is not None else None,
                "username": data.get("name"),
            }
        except httpx.HTTPStatusError as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to fetch Sensr user info: {e.response.text}",
                provider=self.provider_name,
                task="get_provider_user_info",
                user_id=user_id,
                status_code=e.response.status_code,
            )
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch user info: {e.response.text}",
            )
