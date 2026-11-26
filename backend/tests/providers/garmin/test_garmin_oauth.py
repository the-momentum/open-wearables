"""Tests for Garmin OAuth implementation."""

from unittest.mock import MagicMock, create_autospec, patch
from uuid import uuid4

import httpx
import pytest
import redis
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticationMethod
from app.schemas.model_crud.credentials import OAuthTokenResponse, ProviderCredentials, ProviderEndpoints
from app.services.providers.garmin.oauth import GarminOAuth
from app.utils.exceptions import InvalidInputError, ProviderError, ReauthRequiredError
from tests.factories import UserConnectionFactory, UserFactory

USER_ID_URL = "https://apis.garmin.com/partner-gateway/rest/user/id"
PERMISSIONS_URL = "https://apis.garmin.com/partner-gateway/rest/user/permissions"
REGISTRATION_URL = "https://apis.garmin.com/partner-gateway/rest/user/registration"
TOKEN_URL = "https://diauth.garmin.com/di-oauth2-service/oauth/token"

TOKEN_RESPONSE = OAuthTokenResponse(
    access_token="test_access_token",
    token_type="Bearer",
    expires_in=3600,
    refresh_token="test_refresh_token",
)
NEW_TOKENS = {
    "access_token": "new_access_token",
    "refresh_token": "new_refresh_token",
    "expires_in": 3600,
    "token_type": "Bearer",
}


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

    def test_get_authorization_url(self, mocker: MockerFixture, garmin_oauth: GarminOAuth) -> None:
        """Test generating authorization URL with PKCE."""
        mock_get_redis = mocker.patch("app.services.providers.templates.base_oauth.get_redis_client", autospec=True)
        # Arrange
        mock_redis_client = MagicMock(spec=redis.Redis)
        mock_get_redis.return_value = mock_redis_client

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

    def test_get_provider_user_info_success(self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth) -> None:
        """Test fetching Garmin user info successfully (without permissions)."""
        user_id = respx_mock.get(USER_ID_URL).respond(200, json={"userId": "garmin_user_123"})
        permissions = respx_mock.get(PERMISSIONS_URL).respond(
            200, json={"permissions": ["ACTIVITY_EXPORT", "HEALTH_EXPORT"]}
        )

        user_info = garmin_oauth._get_provider_user_info(TOKEN_RESPONSE, "internal_user_id")

        assert user_info["user_id"] == "garmin_user_123"
        assert user_info["username"] is None
        assert user_info["scope"] == "ACTIVITY_EXPORT HEALTH_EXPORT"
        for route in (user_id, permissions):
            assert route.call_count == 1
            assert route.calls.last.request.headers["Authorization"] == "Bearer test_access_token"

    def test_get_provider_user_info_failure(self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth) -> None:
        """Test fetching Garmin user info handles errors gracefully."""
        respx_mock.get(USER_ID_URL).respond(503)

        user_info = garmin_oauth._get_provider_user_info(TOKEN_RESPONSE, "internal_user_id")

        # Assert - should return None values on error
        assert user_info["user_id"] is None
        assert user_info["username"] is None
        assert user_info["scope"] is None

    def test_get_provider_user_info_returns_scope(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        """Test that both API calls succeed and scope is populated."""
        respx_mock.get(USER_ID_URL).respond(200, json={"userId": "garmin_user_456"})
        respx_mock.get(PERMISSIONS_URL).respond(
            200, json={"permissions": ["ACTIVITY_EXPORT", "HEALTH_EXPORT", "WELLNESS_EXPORT"]}
        )

        user_info = garmin_oauth._get_provider_user_info(TOKEN_RESPONSE, "internal_user_id")

        assert user_info["user_id"] == "garmin_user_456"
        assert user_info["scope"] == "ACTIVITY_EXPORT HEALTH_EXPORT WELLNESS_EXPORT"

    def test_get_provider_user_info_permissions_failure_returns_user_id(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        """Test that permissions failure still returns user_id with scope=None."""
        respx_mock.get(USER_ID_URL).respond(200, json={"userId": "garmin_user_789"})
        respx_mock.get(PERMISSIONS_URL).respond(500)

        user_info = garmin_oauth._get_provider_user_info(TOKEN_RESPONSE, "internal_user_id")

        # Assert - user_id returned, scope is None
        assert user_info["user_id"] == "garmin_user_789"
        assert user_info["username"] is None
        assert user_info["scope"] is None

    def test_get_provider_user_info_empty_permissions(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        """Test that empty permissions list results in scope=None."""
        respx_mock.get(USER_ID_URL).respond(200, json={"userId": "garmin_user_abc"})
        respx_mock.get(PERMISSIONS_URL).respond(200, json={"permissions": []})

        user_info = garmin_oauth._get_provider_user_info(TOKEN_RESPONSE, "internal_user_id")

        assert user_info["user_id"] == "garmin_user_abc"
        assert user_info["scope"] is None

    def test_exchange_token_with_pkce(
        self, mocker: MockerFixture, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        """Test token exchange includes PKCE verifier."""
        mocker.patch("app.integrations.redis_client.get_redis_client", autospec=True)
        token = respx_mock.post(TOKEN_URL).respond(200, json=NEW_TOKENS)

        token_response = garmin_oauth._exchange_token("auth_code_123", "test_verifier_abc123")

        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"
        form = httpx.QueryParams(token.calls.last.request.content.decode())
        assert form["code"] == "auth_code_123"
        assert form["code_verifier"] == "test_verifier_abc123"

    def test_refresh_access_token(self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth, db: Session) -> None:
        """Test refreshing access token."""
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            access_token="old_access_token",
            refresh_token="old_refresh_token",
        )
        token = respx_mock.post(TOKEN_URL).respond(200, json=NEW_TOKENS)

        token_response = garmin_oauth.refresh_access_token(db, user.id, "old_refresh_token")

        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"
        form = httpx.QueryParams(token.calls.last.request.content.decode())
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "old_refresh_token"

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

    def test_deregister_user_success(self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth) -> None:
        """Test calling Garmin deregistration endpoint."""
        registration = respx_mock.delete(REGISTRATION_URL).respond(204)

        garmin_oauth.deregister_user("test_access_token")

        assert registration.call_count == 1
        assert registration.calls.last.request.headers["Authorization"] == "Bearer test_access_token"
        assert registration.calls.last.request.extensions["timeout"]["read"] == 30.0

    def test_deregister_user_raises_on_http_error(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        """Test that deregister_user raises on HTTP error (caller handles it)."""
        respx_mock.delete(REGISTRATION_URL).respond(401)

        with pytest.raises(httpx.HTTPStatusError):
            garmin_oauth.deregister_user("expired_token")


class TestOAuthTokenErrors:
    """How the shared OAuth template turns a failed token request into a domain error."""

    @pytest.fixture
    def garmin_oauth(self) -> GarminOAuth:
        return GarminOAuth(
            user_repo=create_autospec(UserRepository, instance=True),
            connection_repo=create_autospec(UserConnectionRepository, instance=True),
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )

    @pytest.mark.parametrize("status_code", [400, 401])
    def test_rejected_refresh_token_revokes_and_requires_reconnection(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth, status_code: int
    ) -> None:
        respx_mock.post(TOKEN_URL).respond(status_code, json={"error": "invalid_grant"})

        with (
            patch.object(garmin_oauth, "revoke_connection", autospec=True) as mock_revoke,
            pytest.raises(ReauthRequiredError),
        ):
            garmin_oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "dead-refresh-token")

        mock_revoke.assert_called_once()

    def test_refresh_during_a_provider_outage_keeps_the_connection(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        respx_mock.post(TOKEN_URL).respond(503, text="maintenance")

        with (
            patch.object(garmin_oauth, "revoke_connection", autospec=True) as mock_revoke,
            pytest.raises(ProviderError) as exc_info,
        ):
            garmin_oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "refresh-token")

        assert (exc_info.value.status_code, exc_info.value.upstream_status) == (502, 503)
        mock_revoke.assert_not_called()

    def test_refresh_without_a_response(self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth) -> None:
        respx_mock.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("connection refused"))

        with pytest.raises(ProviderError) as exc_info:
            garmin_oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "refresh-token")

        assert exc_info.value.detail == "Garmin token refresh failed"

    def test_rejected_authorization_code_is_a_client_error(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        respx_mock.post(TOKEN_URL).respond(400, json={"error": "invalid_grant", "code": "abc"})

        with pytest.raises(InvalidInputError) as exc_info:
            garmin_oauth._exchange_token("expired-code", "verifier")

        assert exc_info.value.detail == "Failed to exchange authorization code"

    def test_code_exchange_during_a_provider_outage(
        self, respx_mock: respx.MockRouter, garmin_oauth: GarminOAuth
    ) -> None:
        respx_mock.post(TOKEN_URL).respond(500, text="oops")

        with pytest.raises(ProviderError) as exc_info:
            garmin_oauth._exchange_token("code", "verifier")

        assert exc_info.value.upstream_status == 500
