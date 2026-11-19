"""
Tests for Polar OAuth implementation.

Tests the PolarOAuth class for OAuth 2.0 authentication flow with Polar API.
"""

import json
from unittest.mock import MagicMock

import httpx
import pytest
import redis
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.schemas.model_crud.credentials import OAuthTokenResponse
from app.services.providers.polar.oauth import PolarOAuth
from tests.factories import UserFactory

USERS_URL = "https://www.polaraccesslink.com/v3/users"
DEREGISTER_URL = "https://www.polaraccesslink.com/v3/users/12345"


class TestPolarOAuthConfiguration:
    """Tests for Polar OAuth configuration and endpoints."""

    def test_polar_oauth_endpoints(self, db: Session) -> None:
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

    def test_polar_oauth_credentials_structure(self, db: Session) -> None:
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

    def test_polar_oauth_uses_basic_auth(self, db: Session) -> None:
        """Test Polar OAuth uses Basic Authentication method."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.schemas.auth import AuthenticationMethod

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

    def test_polar_oauth_does_not_use_pkce(self, db: Session) -> None:
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

    def test_get_authorization_url(self, mocker: MockerFixture, db: Session) -> None:
        """Test generating authorization URL for Polar."""
        mock_redis_client = mocker.patch("app.services.providers.templates.base_oauth.get_redis_client", autospec=True)
        # Arrange
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
        # Verify the mock redis client setex was called
        mock_redis.setex.assert_called()
        # Verify the call was made with the correct state key pattern
        call_args = mock_redis.setex.call_args_list[-1]  # Get the last call
        assert call_args[0][0].startswith("oauth_state:")
        assert call_args[0][1] == 900  # TTL
        assert str(user.id) in call_args[0][2]  # State contains user_id

    def test_authorization_url_includes_scope(self, mocker: MockerFixture, db: Session) -> None:
        """Test authorization URL includes default scope."""
        mock_redis_client = mocker.patch("app.integrations.redis_client.get_redis_client", autospec=True)
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        mock_redis = MagicMock(spec=redis.Redis)
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

    def test_get_provider_user_info_with_x_user_id(self, respx_mock: respx.MockRouter, db: Session) -> None:
        """Test extracting user info when x_user_id is present."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
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

        register = respx_mock.post(USERS_URL).respond(200)

        # Act
        user_info = oauth._get_provider_user_info(token_response, str(user.id))

        # Assert
        assert user_info["user_id"] == "12345"
        assert user_info["username"] is None
        assert register.call_count == 1
        assert register.calls.last.request.headers["Authorization"] == "Bearer test_access_token"

    def test_get_provider_user_info_without_x_user_id(self, db: Session) -> None:
        """Test extracting user info when x_user_id is None."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
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

    def test_register_user_success(self, respx_mock: respx.MockRouter, db: Session) -> None:
        """Test successful user registration with Polar API."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        register = respx_mock.post(USERS_URL).respond(200)

        # Act
        oauth._register_user("test_access_token", str(user.id))

        # Assert
        assert register.call_count == 1
        request = register.calls.last.request
        assert request.headers["Authorization"] == "Bearer test_access_token"
        assert json.loads(request.content)["member-id"] == str(user.id)

    def test_register_user_handles_failure_gracefully(self, respx_mock: respx.MockRouter, db: Session) -> None:
        """Test user registration handles API errors without raising exceptions."""
        # Arrange
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()

        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        register = respx_mock.post(USERS_URL).mock(side_effect=httpx.ConnectError("Network error"))

        # Act & Assert - should not raise exception
        oauth._register_user("test_access_token", str(user.id))
        assert register.call_count == 1
        # User might already be registered, so we handle errors gracefully


class TestPolarUserDeregistration:
    """Tests for Polar user deregistration API call."""

    def _make_oauth(self) -> PolarOAuth:
        from app.models import User
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository

        return PolarOAuth(
            user_repo=UserRepository(User),
            connection_repo=UserConnectionRepository(),
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

    def test_deregister_user_success(self, respx_mock: respx.MockRouter) -> None:
        """Test calling Polar deregistration endpoint."""
        oauth = self._make_oauth()
        deregister = respx_mock.delete(DEREGISTER_URL).respond(204)

        oauth.deregister_user("test_access_token", provider_user_id="12345")

        assert deregister.call_count == 1
        request = deregister.calls.last.request
        assert request.headers["Authorization"] == "Bearer test_access_token"
        assert request.extensions["timeout"]["read"] == 10.0

    def test_deregister_user_raises_on_http_error(self, respx_mock: respx.MockRouter) -> None:
        """Test that deregister_user raises on HTTP error (caller handles it)."""
        oauth = self._make_oauth()
        respx_mock.delete(DEREGISTER_URL).respond(401)

        with pytest.raises(httpx.HTTPStatusError):
            oauth.deregister_user("expired_token", provider_user_id="12345")

    def test_deregister_user_raises_without_provider_user_id(self) -> None:
        """Test that deregister_user requires provider_user_id."""
        oauth = self._make_oauth()

        with pytest.raises(ValueError, match="provider_user_id"):
            oauth.deregister_user("test_access_token")
