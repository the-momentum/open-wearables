from app.config import settings
from app.schemas import AuthenticationMethod, OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class FitbitOAuth(BaseOAuthTemplate):
    """Fitbit OAuth 2.0 with PKCE implementation."""

    use_pkce: bool = True
    auth_method: AuthenticationMethod = AuthenticationMethod.BASIC_AUTH

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://www.fitbit.com/oauth2/authorize",
            token_url="https://api.fitbit.com/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.fitbit_client_id or "",
            client_secret=(
                settings.fitbit_client_secret.get_secret_value()
                if settings.fitbit_client_secret
                else ""
            ),
            redirect_uri=settings.fitbit_redirect_uri,
            default_scope=settings.fitbit_default_scope,
        )

    def _get_provider_user_info(
        self, token_response: OAuthTokenResponse, user_id: str
    ) -> dict[str, str | None]:
        """Fitbit includes user_id directly in the token response."""
        return {
            "user_id": token_response.fitbit_user_id,
            "username": None,
        }
