from app.config import settings
from app.schemas import OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class PolarOAuth(BaseOAuthTemplate):
    """Polar OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://flow.polar.com/oauth2/authorization",
            token_url="https://polarremote.com/v2/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.polar_client_id or "",
            client_secret=(settings.polar_client_secret.get_secret_value() if settings.polar_client_secret else ""),
            redirect_uri=settings.polar_redirect_uri,
            default_scope=settings.polar_default_scope,
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts Polar user ID from token response and registers user."""
        provider_user_id = str(token_response.x_user_id) if token_response.x_user_id is not None else None

        if provider_user_id:
            self._register_user(token_response.access_token, user_id)

        return {"user_id": provider_user_id, "username": None}

    def _register_user(self, access_token: str, member_id: str) -> None:
        """Registers the user with Polar API."""
        import httpx

        try:
            register_url = f"{self.endpoints.api_base_url}/v3/users"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"member-id": member_id}

            httpx.post(register_url, json=payload, headers=headers, timeout=10.0)
        except Exception:
            # Don't fail the entire flow - user might already be registered
            pass
