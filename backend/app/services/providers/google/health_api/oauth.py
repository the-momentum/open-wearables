import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.schemas.auth import AuthenticationMethod
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Google's OpenID Connect userinfo endpoint (requires openid/email scope).
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuth(BaseOAuthTemplate):
    """Google OAuth 2.0 implementation (web server / authorization code flow).

    Google requires ``access_type=offline`` to return a refresh token, and
    ``prompt=consent`` to guarantee one is returned on every consent (Google
    only issues a refresh token on the first consent otherwise). Client
    credentials are sent in the token request body.
    """

    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.google_client_id or "",
            client_secret=(settings.google_client_secret.get_secret_value() if settings.google_client_secret else ""),
            redirect_uri=settings.oauth_redirect_uri(ProviderName.GOOGLE),
            default_scope=settings.google_default_scope,
        )

    def _build_auth_url(self, state: str) -> tuple[str, dict[str, Any] | None]:
        """Build Google's authorization URL.

        Adds the Google-specific parameters the base template doesn't emit:
        ``access_type=offline`` (return a refresh token), ``prompt=consent``
        (always return one), and ``include_granted_scopes=true`` (incremental
        authorization).
        """
        params = {
            "response_type": "code",
            "client_id": self.credentials.client_id,
            "redirect_uri": self.credentials.redirect_uri,
            "state": state,
            "scope": self.credentials.default_scope,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
        return f"{self.endpoints.authorize_url}?{urlencode(params)}", None

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetch the user's Google account id (sub) and email from the userinfo endpoint.

        Best-effort: if the granted scopes don't include ``openid``/``email`` or
        the request fails, fall back to no provider user info rather than failing
        the whole connection.
        """
        try:
            response = httpx.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "user_id": data.get("sub"),
                "username": data.get("email"),
            }
        except Exception as e:
            log_structured(
                logger,
                "warning",
                f"Failed to fetch Google user info: {e}",
                provider=self.provider_name,
                task="get_provider_user_info",
                user_id=user_id,
            )
            return {"user_id": None, "username": None}
