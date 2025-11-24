"""Standard OAuth 2.0 strategy for Suunto and Polar."""

from base64 import b64encode

import jwt

from app.schemas import OAuthTokenResponse, ProviderConfig

from .base_oauth_strategy import BaseOAuthStrategy


class StandardOAuthStrategy(BaseOAuthStrategy):
    """Standard OAuth 2.0 with Basic Auth (Suunto, Polar)."""

    def build_authorization_url(self, config: ProviderConfig, state: str) -> tuple[str, dict | None]:
        """Build standard OAuth 2.0 authorization URL."""
        auth_url = (
            f"{config.authorize_url}?"
            f"response_type=code&"
            f"client_id={config.client_id}&"
            f"redirect_uri={config.redirect_uri}&"
            f"state={state}"
        )

        if config.default_scope:
            auth_url += f"&scope={config.default_scope}"

        return auth_url, None  # No PKCE data for standard OAuth

    def prepare_token_exchange(
        self,
        config: ProviderConfig,
        code: str,
        code_verifier: str | None = None,
    ) -> tuple[dict, dict]:
        """Prepare standard OAuth 2.0 token exchange with Basic Auth."""
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        }

        credentials = f"{config.client_id}:{config.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return token_data, headers

    def prepare_token_refresh(self, config: ProviderConfig, refresh_token: str) -> tuple[dict, dict]:
        """Prepare standard OAuth 2.0 token refresh with Basic Auth."""
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        credentials = f"{config.client_id}:{config.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return refresh_data, headers


class SuuntoOAuthStrategy(StandardOAuthStrategy):
    """Suunto-specific OAuth 2.0 implementation."""

    def extract_provider_user_info(
        self,
        config: ProviderConfig,
        token_response: OAuthTokenResponse,
        user_id: str,
    ) -> dict[str, str | None]:
        """Extract Suunto user info from JWT access token."""
        try:
            decoded = jwt.decode(token_response.access_token, options={"verify_signature": False})
            provider_username = decoded.get("user")
            provider_user_id = decoded.get("sub")
            return {"user_id": provider_user_id, "username": provider_username}
        except Exception:
            # No logger available in strategy
            return {"user_id": None, "username": None}


class PolarOAuthStrategy(StandardOAuthStrategy):
    """Polar-specific OAuth 2.0 implementation."""

    def extract_provider_user_info(
        self,
        config: ProviderConfig,
        token_response: OAuthTokenResponse,
        user_id: str,
    ) -> dict[str, str | None]:
        """Extract Polar user ID from token response and register user."""
        provider_user_id = str(token_response.x_user_id) if token_response.x_user_id is not None else None

        # Register user with Polar API (required before accessing data)
        if provider_user_id:
            try:
                from app.services.polar_service import polar_service

                polar_service.register_user(
                    access_token=token_response.access_token,
                    member_id=user_id,
                )
                # Successfully registered
            except Exception:
                # Don't fail the entire flow - user might already be registered
                pass

        return {"user_id": provider_user_id, "username": None}
