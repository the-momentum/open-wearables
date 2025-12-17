"""
Tests for Polar OAuth implementation.

Tests the PolarOAuth class for OAuth 2.0 authentication flow with Polar API.
"""

from unittest.mock import MagicMock, patch

import httpx
from sqlalchemy.orm import Session

from app.schemas import OAuthTokenResponse
from app.services.providers.polar.oauth import PolarOAuth
from app.tests.utils import create_user


class TestPolarOAuthConfiguration:
    """Tests for Polar OAuth configuration and endpoints."""

    def test_polar_oauth_endpoints(self, db: Session):
        """Test Polar OAuth endpoints are configured correctly."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        endpoints = oauth.endpoints

        # Assert
        assert endpoints.authorize_url == "https://flow.polar.com/oauth2/authorization"
        assert endpoints.token_url == "https://polarremote.com/v2/oauth2/token"

    def test_polar_oauth_credentials_structure(self, db: Session):
        """Test Polar OAuth credentials are structured correctly."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        credentials = oauth.credentials

        # Assert
        assert credentials.client_id is not None
        assert credentials.client_secret is not None
        assert credentials.redirect_uri is not None
        assert isinstance(credentials.client_id, str)
        assert isinstance(credentials.client_secret, str)

    def test_polar_oauth_uses_basic_auth(self, db: Session):
        """Test Polar OAuth uses Basic Authentication method."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.schemas.oauth import AuthenticationMethod

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Assert
        assert oauth.auth_method == AuthenticationMethod.BASIC_AUTH

    def test_polar_oauth_does_not_use_pkce(self, db: Session):
        """Test Polar OAuth does not use PKCE."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Assert
        assert oauth.use_pkce is False


class TestPolarOAuthAuthorization:
    """Tests for Polar OAuth authorization URL generation."""

    @patch("app.integrations.redis_client.get_redis_client")
    def test_get_authorization_url(self, mock_redis_client, db: Session):
        """Test generating authorization URL for Polar."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        mock_redis = MagicMock()
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        auth_url, state = oauth.get_authorization_url(user.id)

        # Assert
        assert "https://flow.polar.com/oauth2/authorization" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert "client_id=" in auth_url
        assert "redirect_uri=" in auth_url
        assert state is not None
        assert len(state) > 0
        mock_redis.setex.assert_called_once()

    @patch("app.integrations.redis_client.get_redis_client")
    def test_authorization_url_includes_scope(self, mock_redis_client, db: Session):
        """Test authorization URL includes default scope."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        mock_redis = MagicMock()
        mock_redis.setex.return_value = True
        mock_redis_client.return_value = mock_redis

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        auth_url, state = oauth.get_authorization_url(user.id)

        # Assert
        # Polar typically uses scope, check if present when configured
        if oauth.credentials.default_scope:
            assert "scope=" in auth_url


class TestPolarOAuthUserInfo:
    """Tests for extracting Polar user info from token response."""

    @patch("httpx.post")
    def test_get_provider_user_info_with_x_user_id(self, mock_post, db: Session):
        """Test extracting user info when x_user_id is present."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
            x_user_id=12345,
        )

        # Mock the registration call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Act
        user_info = oauth._get_provider_user_info(token_response, str(user.id))

        # Assert
        assert user_info["user_id"] == "12345"
        assert user_info["username"] is None
        mock_post.assert_called_once()

    def test_get_provider_user_info_without_x_user_id(self, db: Session):
        """Test extracting user info when x_user_id is None."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
            x_user_id=None,
        )

        # Act
        user_info = oauth._get_provider_user_info(token_response, str(user.id))

        # Assert
        assert user_info["user_id"] is None
        assert user_info["username"] is None


class TestPolarUserRegistration:
    """Tests for Polar user registration API call."""

    @patch("httpx.post")
    def test_register_user_success(self, mock_post, db: Session):
        """Test successful user registration with Polar API."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Act
        oauth._register_user("test_access_token", str(user.id))

        # Assert
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://www.polaraccesslink.com/v3/users"
        assert "Authorization" in call_args[1]["headers"]
        assert "Bearer test_access_token" in call_args[1]["headers"]["Authorization"]
        assert call_args[1]["json"]["member-id"] == str(user.id)

    @patch("httpx.post")
    def test_register_user_handles_failure_gracefully(self, mock_post, db: Session):
        """Test user registration handles API errors without raising exceptions."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = create_user(db)
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        mock_post.side_effect = httpx.RequestError("Network error")

        # Act & Assert - should not raise exception
        oauth._register_user("test_access_token", str(user.id))
        # User might already be registered, so we handle errors gracefully
