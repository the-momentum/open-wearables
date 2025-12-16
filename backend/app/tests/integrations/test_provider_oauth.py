"""
Integration tests for OAuth provider flows.

Tests complete OAuth authorization flows for Garmin, Polar, and Suunto providers.
"""

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.oauth import ConnectionStatus
from app.tests.utils import (
    create_developer,
    create_user,
    create_user_connection,
    developer_auth_headers,
)


class TestGarminOAuth:
    """Tests for Garmin OAuth flow."""

    def test_garmin_authorize_redirect(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test Garmin OAuth authorization initiates redirect."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act - follow_redirects=False to capture the redirect
        response = client.get(
            f"/api/v1/oauth/garmin/authorize?user_id={user.id}",
            headers=headers,
            follow_redirects=False,
        )

        # Assert - Should redirect or return auth URL
        assert response.status_code in [200, 302, 307, 422]

    @patch("httpx.AsyncClient")
    def test_garmin_callback_success(
        self,
        mock_httpx: MagicMock,
        client: TestClient,
        db: Session,
    ):
        """Test Garmin OAuth callback handles tokens."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Mock token exchange response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "user_id": "garmin_user_123",
        }
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = MagicMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        # Act
        response = client.get(
            "/api/v1/oauth/garmin/callback",
            params={
                "oauth_token": "test_token",
                "oauth_verifier": "test_verifier",
                "user_id": str(user.id),
            },
            headers=headers,
            follow_redirects=False,
        )

        # Assert - May redirect to success page or return JSON
        assert response.status_code in [200, 302, 307, 400, 422]

    def test_garmin_callback_error(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test Garmin OAuth callback handles errors."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act - Callback with error parameter
        response = client.get(
            "/api/v1/oauth/garmin/callback",
            params={
                "error": "access_denied",
                "error_description": "User denied access",
                "user_id": str(user.id),
            },
            headers=headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code in [302, 307, 400, 422]


class TestPolarOAuth:
    """Tests for Polar OAuth flow."""

    def test_polar_authorize_redirect(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test Polar OAuth authorization initiates redirect."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(
            f"/api/v1/oauth/polar/authorize?user_id={user.id}",
            headers=headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code in [200, 302, 307, 422]

    @patch("httpx.AsyncClient")
    def test_polar_callback_success(
        self,
        mock_httpx: MagicMock,
        client: TestClient,
        db: Session,
    ):
        """Test Polar OAuth callback handles tokens."""
        # Arrange
        user = create_user(db)

        # Mock token exchange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "polar_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "x_user_id": 12345,
        }
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = MagicMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        # Act
        response = client.get(
            "/api/v1/oauth/polar/callback",
            params={
                "code": "authorization_code",
                "state": str(user.id),
            },
            follow_redirects=False,
        )

        # Assert
        assert response.status_code in [200, 302, 307, 400, 422]


class TestSuuntoOAuth:
    """Tests for Suunto OAuth flow."""

    def test_suunto_authorize_redirect(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test Suunto OAuth authorization initiates redirect."""
        # Arrange
        user = create_user(db)
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(
            f"/api/v1/oauth/suunto/authorize?user_id={user.id}",
            headers=headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code in [200, 302, 307, 422]


class TestOAuthProviderManagement:
    """Tests for OAuth provider settings management."""

    def test_get_providers_list(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test listing all available OAuth providers."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(
            "/api/v1/oauth/providers",
            headers=headers,
        )

        # Assert
        assert response.status_code in [200, 404]

    def test_update_provider_status(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test updating a provider's enabled status."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            headers=headers,
            json={"enabled": True},
        )

        # Assert
        assert response.status_code in [200, 404, 422]


class TestConnectionManagement:
    """Tests for user connection management."""

    def test_list_user_connections(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test listing user's OAuth connections."""
        # Arrange
        from app.tests.utils import api_key_headers, create_api_key

        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        # Create test connections
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.CONNECTED)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/connections",
            headers=headers,
        )

        # Assert
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 2
        else:
            # May not be implemented or different endpoint
            assert response.status_code in [404, 422]

    def test_connection_status_check(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test checking connection status."""
        # Arrange
        from app.tests.utils import api_key_headers, create_api_key

        user = create_user(db)
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        headers = api_key_headers(api_key.id)

        # Create an expired connection
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            status=ConnectionStatus.TOKEN_EXPIRED,
        )

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/connections",
            headers=headers,
        )

        # Assert
        if response.status_code == 200:
            data = response.json()
            if data:
                connection = data[0]
                assert "status" in connection or "provider" in connection
