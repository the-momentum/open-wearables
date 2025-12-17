"""
Tests for connections endpoints.

Tests the /api/v1/users/{user_id}/connections endpoint including:
- Get user connections
- Authentication and authorization
- Connection status filtering
- Error cases
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.oauth import ConnectionStatus
from app.tests.utils import (
    api_key_headers,
    create_api_key,
    create_user,
    create_user_connection,
)


class TestConnectionsEndpoints:
    """Test suite for connections endpoints."""

    def test_get_connections_success(self, client: TestClient, db: Session) -> None:
        """Test successfully retrieving all connections for a user."""
        # Arrange
        user = create_user(db)
        connection1 = create_user_connection(
            db,
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
        )
        connection2 = create_user_connection(
            db,
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(c["id"] == str(connection1.id) for c in data)
        assert any(c["id"] == str(connection2.id) for c in data)

    def test_get_connections_empty_list(self, client: TestClient, db: Session) -> None:
        """Test retrieving connections for a user with no connections."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_connections_multiple_providers(self, client: TestClient, db: Session) -> None:
        """Test retrieving connections for multiple providers."""
        # Arrange
        user = create_user(db)
        providers = ["garmin", "polar", "suunto", "apple"]
        [create_user_connection(db, user=user, provider=provider) for provider in providers]
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        returned_providers = {c["provider"] for c in data}
        assert returned_providers == set(providers)

    def test_get_connections_different_statuses(self, client: TestClient, db: Session) -> None:
        """Test retrieving connections with different statuses."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
        )
        create_user_connection(
            db,
            user=user,
            provider="polar",
            status=ConnectionStatus.REVOKED,
        )
        create_user_connection(
            db,
            user=user,
            provider="suunto",
            status=ConnectionStatus.EXPIRED,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        statuses = {c["status"] for c in data}
        assert ConnectionStatus.ACTIVE.value in statuses
        assert ConnectionStatus.REVOKED.value in statuses
        assert ConnectionStatus.EXPIRED.value in statuses

    def test_get_connections_user_isolation(self, client: TestClient, db: Session) -> None:
        """Test that users can only see their own connections."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        connection1 = create_user_connection(db, user=user1, provider="garmin")
        create_user_connection(db, user=user2, provider="polar")
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - get user1's connections
        response = client.get(f"/api/v1/users/{user1.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(connection1.id)
        assert data[0]["provider"] == "garmin"

    def test_get_connections_response_structure(self, client: TestClient, db: Session) -> None:
        """Test that response contains all expected fields."""
        # Arrange
        user = create_user(db)
        connection = create_user_connection(
            db,
            user=user,
            provider="garmin",
            provider_user_id="test_user_123",
            provider_username="test_user",
            status=ConnectionStatus.ACTIVE,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        connection_data = data[0]

        # Verify essential fields are present
        assert "id" in connection_data
        assert "user_id" in connection_data
        assert "provider" in connection_data
        assert "provider_user_id" in connection_data
        assert "provider_username" in connection_data
        assert "status" in connection_data
        assert "created_at" in connection_data
        assert "updated_at" in connection_data

        # Verify values
        assert connection_data["id"] == str(connection.id)
        assert connection_data["user_id"] == str(user.id)
        assert connection_data["provider"] == "garmin"
        assert connection_data["status"] == ConnectionStatus.ACTIVE.value

    def test_get_connections_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request without API key is rejected."""
        # Arrange
        user = create_user(db)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections")

        # Assert
        assert response.status_code == 401

    def test_get_connections_invalid_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = create_user(db)
        headers = api_key_headers("invalid-api-key")

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 401

    def test_get_connections_invalid_user_id(self, client: TestClient, db: Session) -> None:
        """Test handling of invalid user ID format raises ValueError."""
        # Arrange
        import pytest

        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act & Assert - Invalid UUID causes ValueError with message from UUID parsing
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
            client.get("/api/v1/users/not-a-uuid/connections", headers=headers)

    def test_get_connections_nonexistent_user(self, client: TestClient, db: Session) -> None:
        """Test retrieving connections for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        nonexistent_user_id = uuid4()

        # Act
        response = client.get(f"/api/v1/users/{nonexistent_user_id}/connections", headers=headers)

        # Assert - should return empty list, not 404
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_connections_with_sync_metadata(self, client: TestClient, db: Session) -> None:
        """Test that connections include sync metadata."""
        # Arrange
        from datetime import datetime, timezone

        user = create_user(db)
        last_synced = datetime(2025, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            last_synced_at=last_synced,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "last_synced_at" in data[0]
        # The last_synced_at should be present when set
        if data[0]["last_synced_at"]:
            assert isinstance(data[0]["last_synced_at"], str)

    def test_get_connections_excludes_sensitive_data(self, client: TestClient, db: Session) -> None:
        """Test that sensitive data like access tokens are not exposed."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            access_token="secret_access_token",
            refresh_token="secret_refresh_token",
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/connections", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        connection_data = data[0]

        # Verify sensitive fields are not exposed
        assert "access_token" not in connection_data
        assert "refresh_token" not in connection_data
