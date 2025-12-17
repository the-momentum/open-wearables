"""Tests for Garmin OAuth implementation."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas import AuthenticationMethod, OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.garmin.oauth import GarminOAuth
from app.tests.utils import create_user, create_user_connection


class TestGarminOAuth:
    """Tests for GarminOAuth class."""

    @pytest.fixture
    def garmin_oauth(self, db: Session) -> GarminOAuth:
        """Create GarminOAuth instance for testing."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        return GarminOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )

    def test_endpoints_configuration(self, garmin_oauth: GarminOAuth) -> None:
        """Test OAuth endpoints are correctly configured."""
        endpoints = garmin_oauth.endpoints
        assert isinstance(endpoints, ProviderEndpoints)
        assert endpoints.authorize_url == "https://connect.garmin.com/oauth2Confirm"
        assert endpoints.token_url == "https://diauth.garmin.com/di-oauth2-service/oauth/token"

    def test_credentials_configuration(self, garmin_oauth: GarminOAuth) -> None:
        """Test OAuth credentials are correctly configured."""
        credentials = garmin_oauth.credentials
        assert isinstance(credentials, ProviderCredentials)
        assert credentials.client_id is not None
        assert credentials.client_secret is not None
        assert credentials.redirect_uri is not None

    def test_uses_pkce(self, garmin_oauth: GarminOAuth) -> None:
        """Garmin should use PKCE for OAuth flow."""
        assert garmin_oauth.use_pkce is True

    def test_auth_method_is_body(self, garmin_oauth: GarminOAuth) -> None:
        """Garmin should use body authentication method."""
        assert garmin_oauth.auth_method == AuthenticationMethod.BODY

    @patch("app.integrations.redis_client.get_redis_client")
    def test_get_authorization_url(self, mock_redis: MagicMock, garmin_oauth: GarminOAuth) -> None:
        """Test generating authorization URL with PKCE."""
        # Arrange
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        garmin_oauth.redis_client = mock_redis_client

        user_id = uuid4()

        # Act
        auth_url, state = garmin_oauth.get_authorization_url(user_id)

        # Assert
        assert "https://connect.garmin.com/oauth2Confirm" in auth_url
        assert "client_id=" in auth_url
        assert f"state={state}" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert len(state) > 0
        mock_redis_client.setex.assert_called_once()

    @patch("httpx.get")
    def test_get_provider_user_info_success(
        self,
        mock_httpx_get: MagicMock,
        garmin_oauth: GarminOAuth,
    ) -> None:
        """Test fetching Garmin user info successfully."""
        # Arrange
        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh_token",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"userId": "garmin_user_123"}
        mock_response.raise_for_status.return_value = None
        mock_httpx_get.return_value = mock_response

        # Act
        user_info = garmin_oauth._get_provider_user_info(token_response, "internal_user_id")

        # Assert
        assert user_info["user_id"] == "garmin_user_123"
        assert user_info["username"] is None
        mock_httpx_get.assert_called_once_with(
            "https://apis.garmin.com/wellness-api/rest/user/id",
            headers={"Authorization": "Bearer test_access_token"},
            timeout=30.0,
        )

    @patch("httpx.get")
    def test_get_provider_user_info_failure(
        self,
        mock_httpx_get: MagicMock,
        garmin_oauth: GarminOAuth,
    ) -> None:
        """Test fetching Garmin user info handles errors gracefully."""
        # Arrange
        token_response = OAuthTokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh_token",
        )

        mock_httpx_get.side_effect = httpx.HTTPError("API Error")

        # Act
        user_info = garmin_oauth._get_provider_user_info(token_response, "internal_user_id")

        # Assert - should return None values on error
        assert user_info["user_id"] is None
        assert user_info["username"] is None

    @patch("httpx.post")
    @patch("app.integrations.redis_client.get_redis_client")
    def test_exchange_token_with_pkce(
        self,
        mock_redis: MagicMock,
        mock_httpx_post: MagicMock,
        garmin_oauth: GarminOAuth,
    ) -> None:
        """Test token exchange includes PKCE verifier."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_post.return_value = mock_response

        code = "auth_code_123"
        code_verifier = "test_verifier_abc123"

        # Act
        token_response = garmin_oauth._exchange_token(code, code_verifier)

        # Assert
        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"

        # Verify PKCE verifier was included in request
        call_args = mock_httpx_post.call_args
        assert call_args[1]["data"]["code_verifier"] == code_verifier

    @patch("httpx.post")
    def test_refresh_access_token(
        self,
        mock_httpx_post: MagicMock,
        garmin_oauth: GarminOAuth,
        db: Session,
    ) -> None:
        """Test refreshing access token."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            access_token="old_access_token",
            refresh_token="old_refresh_token",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_post.return_value = mock_response

        # Act
        token_response = garmin_oauth.refresh_access_token(db, user.id, "old_refresh_token")

        # Assert
        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"

    def test_prepare_token_request_uses_body_auth(self, garmin_oauth: GarminOAuth) -> None:
        """Test token request preparation uses body authentication."""
        # Act
        data, headers = garmin_oauth._prepare_token_request("auth_code", "verifier")

        # Assert
        assert "client_id" in data
        assert "client_secret" in data
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == "auth_code"
        assert data["code_verifier"] == "verifier"
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert "Authorization" not in headers  # Body auth, not Basic auth

    def test_prepare_refresh_request_uses_body_auth(self, garmin_oauth: GarminOAuth) -> None:
        """Test refresh token request preparation uses body authentication."""
        # Act
        data, headers = garmin_oauth._prepare_refresh_request("test_refresh_token")

        # Assert
        assert "client_id" in data
        assert "client_secret" in data
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "test_refresh_token"
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert "Authorization" not in headers  # Body auth, not Basic auth
