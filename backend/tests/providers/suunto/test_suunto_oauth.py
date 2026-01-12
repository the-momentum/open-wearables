"""
Tests for SuuntoOAuth.

Tests cover:
- OAuth endpoints configuration
- Credentials configuration
- JWT token decoding for user info
- Authorization URL generation
- Token exchange
- Token refresh
- User info extraction from JWT
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.oauth import OAuthTokenResponse
from app.services.providers.suunto.oauth import SuuntoOAuth


class TestSuuntoOAuth:
    """Test suite for SuuntoOAuth."""

    @pytest.fixture
    def suunto_oauth(self) -> SuuntoOAuth:
        """Create SuuntoOAuth instance for testing."""
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        return SuuntoOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="suunto",
            api_base_url="https://cloudapi.suunto.com",
        )

    def test_endpoints_configuration(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should return correct OAuth endpoints."""
        # Act
        endpoints = suunto_oauth.endpoints

        # Assert
        assert endpoints.authorize_url == "https://cloudapi-oauth.suunto.com/oauth/authorize"
        assert endpoints.token_url == "https://cloudapi-oauth.suunto.com/oauth/token"

    def test_credentials_configuration(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should return credentials with client ID, secret, and subscription key."""
        # Act
        credentials = suunto_oauth.credentials

        # Assert
        assert credentials.client_id is not None
        assert credentials.client_secret is not None
        assert credentials.redirect_uri is not None
        # Subscription key may be None if not configured
        assert hasattr(credentials, "subscription_key")

    def test_get_authorization_url(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should generate authorization URL with correct parameters."""
        # Arrange
        user_id = uuid4()

        # Act
        auth_url, state = suunto_oauth.get_authorization_url(user_id)

        # Assert
        assert "https://cloudapi-oauth.suunto.com/oauth/authorize" in auth_url
        assert "client_id=" in auth_url
        assert f"state={state}" in auth_url
        assert "response_type=code" in auth_url
        assert len(state) > 0

    def test_extract_user_info_from_jwt_success(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should extract user info from JWT access token."""
        # Arrange
        test_payload = {
            "sub": "suunto_user_12345",
            "user": "test_suunto_user",
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
        }
        # Create JWT without signature verification
        access_token = jwt.encode(test_payload, "secret", algorithm="HS256")

        token_response = OAuthTokenResponse(
            access_token=access_token,
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
        )

        # Act
        user_info = suunto_oauth._get_provider_user_info(token_response, "test_user_id")

        # Assert
        assert user_info["user_id"] == "suunto_user_12345"
        assert user_info["username"] == "test_suunto_user"

    def test_extract_user_info_from_jwt_missing_fields(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should handle JWT with missing user fields."""
        # Arrange
        test_payload = {
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
            # Missing 'sub' and 'user' fields
        }
        access_token = jwt.encode(test_payload, "secret", algorithm="HS256")

        token_response = OAuthTokenResponse(
            access_token=access_token,
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
        )

        # Act
        user_info = suunto_oauth._get_provider_user_info(token_response, "test_user_id")

        # Assert
        assert user_info["user_id"] is None
        assert user_info["username"] is None

    def test_extract_user_info_from_invalid_jwt(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should handle invalid JWT gracefully."""
        # Arrange
        token_response = OAuthTokenResponse(
            access_token="invalid.jwt.token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
        )

        # Act
        user_info = suunto_oauth._get_provider_user_info(token_response, "test_user_id")

        # Assert
        assert user_info["user_id"] is None
        assert user_info["username"] is None

    @patch("httpx.post")
    def test_exchange_token_success(self, mock_post: MagicMock, suunto_oauth: SuuntoOAuth, db: Session) -> None:
        """Should exchange authorization code for tokens."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        token_response = suunto_oauth._exchange_token("test_code", None)

        # Assert
        assert token_response.access_token == "test_access_token"
        assert token_response.refresh_token == "test_refresh_token"
        assert token_response.expires_in == 3600
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_refresh_access_token_success(self, mock_post: MagicMock, suunto_oauth: SuuntoOAuth, db: Session) -> None:
        """Should refresh access token using refresh token."""
        # Arrange
        from tests.factories import UserConnectionFactory, UserFactory

        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="suunto",
            refresh_token="old_refresh_token",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Act
        token_response = suunto_oauth.refresh_access_token(db, user.id, "old_refresh_token")

        # Assert
        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"
        mock_post.assert_called_once()

    def test_uses_basic_auth_method(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should use Basic Auth for token exchange."""
        # Act
        from app.schemas.oauth import AuthenticationMethod

        # Assert
        assert suunto_oauth.auth_method == AuthenticationMethod.BASIC_AUTH

    def test_does_not_use_pkce(self, suunto_oauth: SuuntoOAuth) -> None:
        """Should not use PKCE for authorization flow."""
        # Assert
        assert suunto_oauth.use_pkce is False
