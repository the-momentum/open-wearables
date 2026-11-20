"""
Tests for Ultrahuman OAuth implementation.

Tests the UltrahumanOAuth class for OAuth 2.0 authentication flow with Ultrahuman Partnership API.
"""

from unittest.mock import MagicMock

import httpx
import redis
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth.authentication_method import AuthenticationMethod
from app.schemas.model_crud.credentials import OAuthTokenResponse
from app.services.providers.ultrahuman.oauth import UltrahumanOAuth
from tests.factories import UserFactory


class TestUltrahumanOAuthConfiguration:
    """Tests for Ultrahuman OAuth configuration and endpoints."""

    def test_ultrahuman_oauth_endpoints(self, db: Session) -> None:
        """Test Ultrahuman OAuth endpoints are configured correctly."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Act
        endpoints = oauth.endpoints

        # Assert
        assert endpoints.authorize_url == "https://auth.ultrahuman.com/authorise"
        assert endpoints.token_url == "https://partner.ultrahuman.com/api/partners/oauth/token"

    def test_ultrahuman_oauth_credentials_structure(self, db: Session) -> None:
        """Test Ultrahuman OAuth credentials are structured correctly."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Act
        credentials = oauth.credentials

        # Assert
        assert credentials.client_id is not None
        assert credentials.client_secret is not None
        assert credentials.redirect_uri is not None
        assert isinstance(credentials.client_id, str)
        assert isinstance(credentials.client_secret, str)

    def test_ultrahuman_oauth_uses_body_auth(self, db: Session) -> None:
        """Test Ultrahuman OAuth uses BODY Authentication method."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Assert
        assert oauth.auth_method == AuthenticationMethod.BODY

    def test_ultrahuman_oauth_does_not_use_pkce(self, db: Session) -> None:
        """Test Ultrahuman OAuth does not use PKCE."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Assert
        assert oauth.use_pkce is False


class TestUltrahumanOAuthAuthorization:
    """Tests for Ultrahuman OAuth authorization URL generation."""

    def test_get_authorization_url(self, mocker: MockerFixture, db: Session) -> None:
        """Test generating authorization URL for Ultrahuman."""
        mock_redis_client = mocker.patch("app.services.providers.templates.base_oauth.get_redis_client", autospec=True)
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        # Setup mock redis before creating OAuth instance
        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Act
        auth_url, state = oauth.get_authorization_url(user.id)

        # Assert
        assert "https://auth.ultrahuman.com/authorise" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert "client_id=" in auth_url
        assert "redirect_uri=" in auth_url
        assert state is not None
        assert len(state) > 0
        # Verify the mock redis client setex was called
        mock_redis.setex.assert_called()
        # Verify the call was made with the correct state key pattern
        call_args = mock_redis.setex.call_args_list[-1]  # Get the last call
        assert call_args[0][0].startswith("oauth_state:")
        assert call_args[0][1] == 900  # TTL
        assert str(user.id) in call_args[0][2]  # State contains user_id

    def test_authorization_url_includes_scope(self, mocker: MockerFixture, db: Session) -> None:
        """Test authorization URL includes default scope."""
        mock_redis_client = mocker.patch("app.services.providers.templates.base_oauth.get_redis_client", autospec=True)
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        mock_redis = MagicMock(spec=redis.Redis)
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        # Act
        auth_url, state = oauth.get_authorization_url(user.id)

        # Assert
        # Ultrahuman uses scope, check if present when configured
        if oauth.credentials.default_scope:
            assert "scope=" in auth_url


class TestUltrahumanOAuthUserInfo:
    """Tests for extracting Ultrahuman user info from token response."""

    def test_get_provider_user_info_with_user_id(self, respx_mock: respx.MockRouter, db: Session) -> None:
        """Test extracting user info when user_id is present."""
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
        )

        profile = respx_mock.get("https://partner.ultrahuman.com/user_data/user_info").respond(
            200, json={"user_id": "test_user_123", "email": "test@example.com"}
        )

        # Act
        user_info = oauth._get_provider_user_info(token_response, str(user.id))

        # Assert
        assert user_info["user_id"] == "test_user_123"
        assert user_info["username"] == "test@example.com"
        assert profile.call_count == 1
        assert profile.calls.last.request.headers["Authorization"] == "Bearer test_access_token"

    def test_get_provider_user_info_handles_failure(self, respx_mock: respx.MockRouter, db: Session) -> None:
        """Test extracting user info when API call fails."""
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = UltrahumanOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="ultrahuman",
            api_base_url="https://partner.ultrahuman.com",
        )

        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
        )

        respx_mock.get("https://partner.ultrahuman.com/user_data/user_info").mock(
            side_effect=httpx.ConnectError("Network error")
        )

        # Act
        user_info = oauth._get_provider_user_info(token_response, str(user.id))

        # Assert
        assert user_info["user_id"] is None
        assert user_info["username"] is None
