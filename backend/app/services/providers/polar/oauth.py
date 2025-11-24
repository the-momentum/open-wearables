from app.config import settings
from app.schemas.oauth import OAuthTokenResponse, ProviderConfig
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class PolarOAuth(BaseOAuthTemplate):
    """Polar OAuth 2.0 implementation."""

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="polar",
            client_id=settings.polar_client_id or "",
            client_secret=(settings.polar_client_secret.get_secret_value() if settings.polar_client_secret else ""),
            redirect_uri=settings.polar_redirect_uri,
            authorize_url=settings.polar_authorize_url,
            token_url=settings.polar_token_url,
            api_base_url=settings.polar_api_base_url,
            default_scope=settings.polar_default_scope,
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts Polar user ID from token response and registers user."""
        provider_user_id = str(token_response.x_user_id) if token_response.x_user_id is not None else None

        # Register user with Polar API (required before accessing data)
        if provider_user_id:
            try:
                # Note: We need to import polar_service here or implement registration logic directly
                # For now, we'll assume the registration logic should be here or in a service
                # To avoid circular imports if polar_service uses this, we might need to refactor
                # But since we are moving to new structure, we should probably implement registration here
                # or call a method on the template if it was common.
                
                # Since registration is unique to Polar, we can implement it here using httpx
                import httpx
                
                register_url = f"{self.config.api_base_url}/v3/users"
                headers = {
                    "Authorization": f"Bearer {token_response.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                payload = {"member-id": user_id}
                
                httpx.post(register_url, json=payload, headers=headers, timeout=10.0)
                
            except Exception:
                # Don't fail the entire flow - user might already be registered
                pass

        return {"user_id": provider_user_id, "username": None}
