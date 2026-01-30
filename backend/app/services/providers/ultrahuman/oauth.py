"""Ultrahuman Ring Air OAuth 2.0 implementation."""

import logging

import httpx

from app.config import settings
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class UltrahumanOAuth(BaseOAuthTemplate):
    """Ultrahuman Partnership API OAuth 2.0 implementation.

    Ultrahuman uses standard OAuth 2.0 with authorization code grant.
    API documentation: https://vision.ultrahuman.com/developer-docs
    """

    def __init__(
        self,
        user_repo: UserRepository,
        connection_repo: UserConnectionRepository,
        provider_name: str,
        api_base_url: str,
    ):
        super().__init__(user_repo, connection_repo, provider_name, api_base_url)
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def endpoints(self) -> ProviderEndpoints:
        """OAuth endpoints for authorization and token exchange."""
        return ProviderEndpoints(
            authorize_url="https://auth.ultrahuman.com/authorise",
            token_url="https://partner.ultrahuman.com/api/partners/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        """OAuth credentials from environment variables."""
        return ProviderCredentials(
            client_id=settings.ultrahuman_client_id or "",
            client_secret=(
                settings.ultrahuman_client_secret.get_secret_value() if settings.ultrahuman_client_secret else ""
            ),
            redirect_uri=settings.ultrahuman_redirect_uri,
            default_scope=settings.ultrahuman_default_scope,
        )

    # OAuth configuration
    use_pkce = False  # Ultrahuman doesn't require PKCE
    auth_method = AuthenticationMethod.BODY  # Credentials in request body

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetches Ultrahuman user profile via API.

        Returns user ID and username from Ultrahuman profile data.
        Endpoint: /user_data/user_info
        """
        try:
            profile_response = httpx.get(
                f"{self.api_base_url}/user_data/user_info",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
            provider_user_id = profile_data.get("user_id")
            provider_username = profile_data.get("username") or profile_data.get("email")
            return {
                "user_id": str(provider_user_id) if provider_user_id else None,
                "username": provider_username,
            }
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error fetching Ultrahuman user profile for user {user_id}: {e}")
            return {"user_id": None, "username": None}
        except Exception as e:
            self.logger.error(f"Unexpected error fetching Ultrahuman user profile for user {user_id}: {e}")
            return {"user_id": None, "username": None}
