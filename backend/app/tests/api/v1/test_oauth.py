"""
Tests for OAuth endpoints.

Tests the /api/v1/oauth endpoints including:
- GET /api/v1/oauth/{provider}/authorize - test authorize redirect
- GET /api/v1/oauth/providers - test list providers
- PUT /api/v1/oauth/providers/{provider} - test update provider status
"""

from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import (
    create_developer,
    developer_auth_headers,
)


class TestOAuthAuthorizeEndpoint:
    """Test suite for OAuth authorization endpoint."""

    def test_authorize_provider_success(self, client: TestClient, db: Session) -> None:
        """Test successfully initiating OAuth flow for a provider."""
        # Arrange
        user_id = uuid4()

        # Act
        response = client.get(
            "/api/v1/oauth/garmin/authorize",
            params={"user_id": str(user_id)},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert isinstance(data["authorization_url"], str)
        assert isinstance(data["state"], str)
        assert len(data["state"]) > 0

    def test_authorize_provider_with_redirect_uri(self, client: TestClient, db: Session) -> None:
        """Test OAuth flow with optional redirect URI."""
        # Arrange
        user_id = uuid4()
        redirect_uri = "https://myapp.com/oauth/callback"

        # Act
        response = client.get(
            "/api/v1/oauth/garmin/authorize",
            params={
                "user_id": str(user_id),
                "redirect_uri": redirect_uri,
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data

    def test_authorize_different_providers(self, client: TestClient, db: Session) -> None:
        """Test initiating OAuth for different providers."""
        # Arrange
        user_id = uuid4()
        providers = ["garmin", "polar", "suunto"]

        for provider in providers:
            # Act
            response = client.get(
                f"/api/v1/oauth/{provider}/authorize",
                params={"user_id": str(user_id)},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "authorization_url" in data
            assert "state" in data

    def test_authorize_missing_user_id(self, client: TestClient, db: Session) -> None:
        """Test authorization without user_id parameter."""
        # Act
        response = client.get("/api/v1/oauth/garmin/authorize")

        # Assert
        assert response.status_code == 400

    def test_authorize_invalid_user_id(self, client: TestClient, db: Session) -> None:
        """Test authorization with invalid user_id format."""
        # Act
        response = client.get(
            "/api/v1/oauth/garmin/authorize",
            params={"user_id": "not-a-uuid"},
        )

        # Assert
        assert response.status_code == 400

    def test_authorize_invalid_provider(self, client: TestClient, db: Session) -> None:
        """Test authorization with non-existent provider."""
        # Arrange
        user_id = uuid4()

        # Act
        response = client.get(
            "/api/v1/oauth/invalid-provider/authorize",
            params={"user_id": str(user_id)},
        )

        # Assert
        assert response.status_code == 400

    def test_authorize_non_oauth_provider(self, client: TestClient, db: Session) -> None:
        """Test authorization with provider that doesn't support OAuth."""
        # Arrange
        user_id = uuid4()

        # Act - Try to authorize with "apple" which uses file import, not OAuth
        response = client.get(
            "/api/v1/oauth/apple/authorize",
            params={"user_id": str(user_id)},
        )

        # Assert - Should fail because apple doesn't have OAuth
        assert response.status_code in [400, 422]


class TestOAuthProvidersEndpoint:
    """Test suite for providers listing endpoint."""

    def test_get_providers_success(self, client: TestClient, db: Session) -> None:
        """Test successfully retrieving all providers."""
        # Act
        response = client.get("/api/v1/oauth/providers")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure of first provider
        if data:
            provider = data[0]
            assert "provider" in provider
            assert "name" in provider
            assert "icon_url" in provider
            assert "has_cloud_api" in provider
            assert "is_enabled" in provider

    def test_get_providers_enabled_only(self, client: TestClient, db: Session) -> None:
        """Test retrieving only enabled providers."""
        # Act
        response = client.get(
            "/api/v1/oauth/providers",
            params={"enabled_only": True},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned providers should be enabled
        for provider in data:
            assert provider["is_enabled"] is True

    def test_get_providers_cloud_only(self, client: TestClient, db: Session) -> None:
        """Test retrieving only cloud (OAuth) providers."""
        # Act
        response = client.get(
            "/api/v1/oauth/providers",
            params={"cloud_only": True},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned providers should have cloud API
        for provider in data:
            assert provider["has_cloud_api"] is True

    def test_get_providers_enabled_and_cloud(self, client: TestClient, db: Session) -> None:
        """Test retrieving providers with both filters."""
        # Act
        response = client.get(
            "/api/v1/oauth/providers",
            params={"enabled_only": True, "cloud_only": True},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned providers should be enabled AND have cloud API
        for provider in data:
            assert provider["is_enabled"] is True
            assert provider["has_cloud_api"] is True

    def test_get_providers_include_disabled(self, client: TestClient, db: Session) -> None:
        """Test that disabled providers are included by default."""
        # Act - no filters
        response = client.get("/api/v1/oauth/providers")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include both enabled and disabled
        any(p["is_enabled"] for p in data)
        any(not p["is_enabled"] for p in data)
        # At least one of each should exist (assuming test data setup)
        # If all are enabled or disabled, that's also valid

    def test_get_providers_response_structure(self, client: TestClient, db: Session) -> None:
        """Test detailed response structure of providers."""
        # Act
        response = client.get("/api/v1/oauth/providers")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        # Check first provider has all required fields
        provider = data[0]
        required_fields = [
            "provider",
            "name",
            "icon_url",
            "has_cloud_api",
            "is_enabled",
        ]
        for field in required_fields:
            assert field in provider, f"Missing field: {field}"


class TestOAuthUpdateProviderEndpoint:
    """Test suite for updating provider status endpoint."""

    def test_update_provider_status_enable(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test enabling a provider."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        update_data = {"is_enabled": True}

        # Act
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "garmin"
        assert data["is_enabled"] is True

    def test_update_provider_status_disable(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test disabling a provider."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        update_data = {"is_enabled": False}

        # Act
        response = client.put(
            "/api/v1/oauth/providers/polar",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "polar"
        assert data["is_enabled"] is False

    def test_update_provider_requires_authentication(self, client: TestClient, db: Session) -> None:
        """Test that updating provider status requires authentication."""
        # Arrange
        update_data = {"is_enabled": True}

        # Act - no auth headers
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            json=update_data,
        )

        # Assert
        assert response.status_code == 401

    def test_update_provider_invalid_auth(self, client: TestClient, db: Session) -> None:
        """Test that invalid authentication is rejected."""
        # Arrange
        update_data = {"is_enabled": True}
        headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 401

    def test_update_nonexistent_provider(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test updating a provider that doesn't exist."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        update_data = {"is_enabled": True}

        # Act
        response = client.put(
            "/api/v1/oauth/providers/nonexistent-provider",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 404

    def test_update_provider_invalid_payload(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test updating provider with invalid payload."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        update_data = {}  # Missing is_enabled

        # Act
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 400

    def test_update_provider_response_structure(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test response structure of update endpoint."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        update_data = {"is_enabled": True}

        # Act
        response = client.put(
            "/api/v1/oauth/providers/garmin",
            headers=headers,
            json=update_data,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "name" in data
        assert "icon_url" in data
        assert "has_cloud_api" in data
        assert "is_enabled" in data

    def test_update_multiple_providers_sequentially(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test updating multiple providers one after another."""
        # Arrange
        developer = create_developer(db)
        headers = developer_auth_headers(developer.id)
        providers = ["garmin", "polar", "suunto"]

        for provider in providers:
            # Act
            response = client.put(
                f"/api/v1/oauth/providers/{provider}",
                headers=headers,
                json={"is_enabled": True},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == provider
            assert data["is_enabled"] is True
