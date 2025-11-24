"""Base OAuth strategy for provider-specific implementations."""

from abc import ABC, abstractmethod

from app.schemas import OAuthTokenResponse, ProviderConfig


class BaseOAuthStrategy(ABC):
    """Base class for provider-specific OAuth implementations."""

    @abstractmethod
    def build_authorization_url(
        self,
        config: ProviderConfig,
        state: str,
    ) -> tuple[str, dict | None]:
        """Build provider-specific authorization URL.

        Args:
            config: Provider configuration
            state: OAuth state parameter

        Returns:
            tuple: (authorization_url, pkce_data_or_None)
                   pkce_data is dict with 'code_verifier' for PKCE flows
        """
        pass

    @abstractmethod
    def prepare_token_exchange(
        self,
        config: ProviderConfig,
        code: str,
        code_verifier: str | None = None,
    ) -> tuple[dict, dict]:
        """Prepare token exchange request data and headers.

        Args:
            config: Provider configuration
            code: Authorization code
            code_verifier: PKCE code verifier (for PKCE flows)

        Returns:
            tuple: (request_data, headers)
        """
        pass

    @abstractmethod
    def prepare_token_refresh(
        self,
        config: ProviderConfig,
        refresh_token: str,
    ) -> tuple[dict, dict]:
        """Prepare token refresh request data and headers.

        Args:
            config: Provider configuration
            refresh_token: Refresh token

        Returns:
            tuple: (request_data, headers)
        """
        pass

    @abstractmethod
    def extract_provider_user_info(
        self,
        config: ProviderConfig,
        token_response: OAuthTokenResponse,
        user_id: str,
    ) -> dict[str, str | None]:
        """Extract provider user ID and username from token response.

        Args:
            config: Provider configuration
            token_response: OAuth token response
            user_id: Internal user ID (for providers that need it)

        Returns:
            dict with keys: 'user_id' (provider user ID), 'username' (optional)
        """
        pass
