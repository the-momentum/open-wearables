"""
Tests for user management endpoints.

Tests cover:
- GET /api/v1/users - list all users
- GET /api/v1/users/{user_id} - get user by ID
- POST /api/v1/users - create new user
- PATCH /api/v1/users/{user_id} - update user
- DELETE /api/v1/users/{user_id} - delete user
- Connection expansion, connection filters, and sorting on the list endpoint
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.auth import ConnectionStatus
from tests.factories import ApiKeyFactory, DeveloperFactory, UserConnectionFactory, UserFactory
from tests.utils import api_key_headers, developer_auth_headers


class TestListUsers:
    """Tests for GET /api/v1/users."""

    def test_list_users_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test listing users with valid API key."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        user1 = UserFactory(email="user1@example.com", first_name="John", last_name="Doe")
        user2 = UserFactory(email="user2@example.com", first_name="Jane", last_name="Smith")
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"{api_v1_prefix}/users", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        # Response is paginated format with 'items' list
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 2
        assert "total" in data
        assert "page" in data
        assert "limit" in data

        # Find our test users
        user_ids = [str(user1.id), str(user2.id)]
        found_users = [u for u in data["items"] if u["id"] in user_ids]
        assert len(found_users) == 2

    def test_list_users_empty(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test listing users when no users exist."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"{api_v1_prefix}/users", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        # Response is paginated format with 'items' list
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_users_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test listing users fails without API key."""
        # Act
        response = client.get(f"{api_v1_prefix}/users")

        # Assert
        assert response.status_code == 401

    def test_list_users_invalid_api_key(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test listing users fails with invalid API key."""
        # Act
        response = client.get(
            f"{api_v1_prefix}/users",
            headers={"X-Open-Wearables-API-Key": "invalid_key"},
        )

        # Assert
        assert response.status_code == 401

    def test_list_users_skips_invalid_email_rows(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test listing users skips rows with invalid emails instead of returning 500."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        UserFactory(email="user1@ci.local", first_name="John", last_name="Doe")
        user2 = UserFactory(email="user2@example.com", first_name="Jane", last_name="Smith")
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"{api_v1_prefix}/users", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Find our test users
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(user2.id)
        assert data["total"] == 1


class TestGetUser:
    """Tests for GET /api/v1/users/{user_id}."""

    def test_get_user_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting user by ID with valid API key."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        user = UserFactory(email="user@example.com", first_name="John", last_name="Doe")
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"{api_v1_prefix}/users/{user.id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == "user@example.com"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "created_at" in data

    def test_get_user_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting non-existent user raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.get(f"{api_v1_prefix}/users/{fake_id}", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_get_user_invalid_uuid(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting user with invalid UUID format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"{api_v1_prefix}/users/not-a-uuid", headers=headers)

        # Assert
        assert response.status_code == 400

    def test_get_user_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting user fails without API key."""
        # Arrange
        user = UserFactory(email="user@example.com")

        # Act
        response = client.get(f"{api_v1_prefix}/users/{user.id}")

        # Assert
        assert response.status_code == 401


class TestCreateUser:
    """Tests for POST /api/v1/users."""

    def test_create_user_full_data(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating user with all fields."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        payload = {
            "email": "newuser@example.com",
            "first_name": "Alice",
            "last_name": "Johnson",
            "external_user_id": "ext123",
        }

        # Act
        response = client.post(f"{api_v1_prefix}/users", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["first_name"] == "Alice"
        assert data["last_name"] == "Johnson"
        assert data["external_user_id"] == "ext123"
        assert "id" in data
        assert "created_at" in data

        # Verify in database
        from app.services import user_service

        user = user_service.get(db, data["id"])
        assert user is not None
        assert user.email == "newuser@example.com"

    def test_create_user_minimal_data(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating user with minimal fields."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        payload = {}

        # Act
        response = client.post(f"{api_v1_prefix}/users", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "created_at" in data

    def test_create_user_only_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating user with only email."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        payload = {"email": "onlyemail@example.com"}

        # Act
        response = client.post(f"{api_v1_prefix}/users", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "onlyemail@example.com"
        assert data["first_name"] is None
        assert data["last_name"] is None

    def test_create_user_invalid_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating user with invalid email format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        payload = {"email": "not-an-email"}

        # Act
        response = client.post(f"{api_v1_prefix}/users", json=payload, headers=headers)

        # Assert
        assert response.status_code == 400

    def test_create_user_name_too_long(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating user with name exceeding max length."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.id)
        payload = {
            "first_name": "a" * 101,  # Max is 100
            "last_name": "Smith",
        }

        # Act
        response = client.post(f"{api_v1_prefix}/users", json=payload, headers=headers)

        # Assert
        assert response.status_code == 400

    def test_create_user_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test creating user fails without API key."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/users",
            json={"email": "test@example.com"},
        )

        # Assert
        assert response.status_code == 401


class TestUpdateUser:
    """Tests for PATCH /api/v1/users/{user_id}."""

    def test_update_user_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user email."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(email="old@example.com", first_name="John")
        headers = developer_auth_headers(developer.id)
        payload = {"email": "new@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["first_name"] == "John"

        # Verify in database
        db.refresh(user)
        assert user.email == "new@example.com"

    def test_update_user_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(first_name="John", last_name="Doe")
        headers = developer_auth_headers(developer.id)
        payload = {"first_name": "Jane", "last_name": "Smith"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Smith"

        # Verify in database
        db.refresh(user)
        assert user.first_name == "Jane"
        assert user.last_name == "Smith"

    def test_update_user_external_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user external ID."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(external_user_id="old_id")
        headers = developer_auth_headers(developer.id)
        payload = {"external_user_id": "new_id"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["external_user_id"] == "new_id"

        # Verify in database
        db.refresh(user)
        assert user.external_user_id == "new_id"

    def test_update_user_empty_payload(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user with empty payload."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(email="user@example.com", first_name="John")
        headers = developer_auth_headers(developer.id)
        payload = {}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["first_name"] == "John"

    def test_update_user_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating non-existent user raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_id = "00000000-0000-0000-0000-000000000000"
        payload = {"email": "new@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{fake_id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 404

    def test_update_user_invalid_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user with invalid email."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(email="user@example.com")
        headers = developer_auth_headers(developer.id)
        payload = {"email": "not-an-email"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 400

    def test_update_user_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user fails without authentication."""
        # Arrange
        user = UserFactory(email="user@example.com")
        payload = {"email": "new@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload)

        # Assert
        assert response.status_code == 401

    def test_update_user_requires_bearer_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating user requires bearer token, not API key."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        user = UserFactory(email="user@example.com")
        headers = api_key_headers(api_key.id)
        payload = {"email": "new@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/users/{user.id}", json=payload, headers=headers)

        # Assert - API key auth is rejected, requires bearer token
        assert response.status_code == 401


class TestDeleteUser:
    """Tests for DELETE /api/v1/users/{user_id}."""

    def test_delete_user_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting user successfully."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        user = UserFactory(email="user@example.com", first_name="John")
        headers = developer_auth_headers(developer.id)
        user_id = user.id

        # Act
        response = client.delete(f"{api_v1_prefix}/users/{user_id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user_id)
        assert data["email"] == "user@example.com"

        # Verify user is deleted from database
        from app.services import user_service

        deleted_user = user_service.get(db, user_id, raise_404=False)
        assert deleted_user is None

    def test_delete_user_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting non-existent user raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.delete(f"{api_v1_prefix}/users/{fake_id}", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_delete_user_invalid_uuid(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting user with invalid UUID format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/users/not-a-uuid", headers=headers)

        # Assert
        assert response.status_code == 400

    def test_delete_user_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting user fails without authentication."""
        # Arrange
        user = UserFactory(email="user@example.com")

        # Act
        response = client.delete(f"{api_v1_prefix}/users/{user.id}")

        # Assert
        assert response.status_code == 401

    def test_delete_user_requires_bearer_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting user requires bearer token, not API key."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        user = UserFactory(email="user@example.com")
        headers = api_key_headers(api_key.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/users/{user.id}", headers=headers)

        # Assert - API key auth is rejected, requires bearer token
        assert response.status_code == 401


class TestListUsersConnections:
    """Tests for the connections expansion on GET /api/v1/users."""

    @pytest.fixture
    def headers(self) -> dict[str, str]:
        developer = DeveloperFactory(email="connections@example.com", password="test123")
        return api_key_headers(ApiKeyFactory(developer=developer).id)

    def test_connections_absent_by_default(self, client: TestClient, api_v1_prefix: str, headers: dict) -> None:
        """Test that connections are omitted unless the expansion is requested."""
        # Arrange
        user = UserFactory(email="default@example.com")
        UserConnectionFactory(user=user, provider="garmin")

        # Act
        response = client.get(f"{api_v1_prefix}/users", headers=headers)

        # Assert
        assert response.status_code == 200
        item = next(u for u in response.json()["items"] if u["id"] == str(user.id))
        assert item["connections"] is None
        assert item["has_active_connection"] is True

    def test_include_connections_returns_every_status(
        self, client: TestClient, api_v1_prefix: str, headers: dict
    ) -> None:
        """Test that the expansion lists all connections, not only active ones."""
        # Arrange
        synced_at = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        user = UserFactory(email="expanded@example.com")
        UserConnectionFactory(user=user, provider="whoop", status=ConnectionStatus.REVOKED)
        UserConnectionFactory(user=user, provider="garmin", last_synced_at=synced_at)

        # Act
        response = client.get(f"{api_v1_prefix}/users?include=connections", headers=headers)

        # Assert
        assert response.status_code == 200
        item = next(u for u in response.json()["items"] if u["id"] == str(user.id))
        assert item["connections"] == [
            {"provider": "garmin", "status": "active", "last_synced_at": "2026-03-01T12:00:00Z"},
            {"provider": "whoop", "status": "revoked", "last_synced_at": None},
        ]
        assert item["last_synced_provider"] == "garmin"

    def test_include_connections_empty_for_unconnected_user(
        self, client: TestClient, api_v1_prefix: str, headers: dict
    ) -> None:
        """Test that a user without connections gets an empty list, not null."""
        # Arrange
        user = UserFactory(email="unconnected@example.com")

        # Act
        response = client.get(f"{api_v1_prefix}/users?include=connections", headers=headers)

        # Assert
        item = next(u for u in response.json()["items"] if u["id"] == str(user.id))
        assert item["connections"] == []
        assert item["has_active_connection"] is False
        assert item["last_synced_provider"] is None

    def test_unknown_include_is_rejected(self, client: TestClient, api_v1_prefix: str, headers: dict) -> None:
        """Test that a typo in the expansion fails loudly instead of being ignored."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?include=connection", headers=headers)

        # Assert
        assert response.status_code == 400


class TestListUsersFilters:
    """Tests for the connection filters and sorting on GET /api/v1/users."""

    @pytest.fixture
    def headers(self) -> dict[str, str]:
        developer = DeveloperFactory(email="filters@example.com", password="test123")
        return api_key_headers(ApiKeyFactory(developer=developer).id)

    @pytest.fixture
    def users(self) -> dict[str, User]:
        """Three users: an active Garmin sync, a revoked Whoop, and no connection at all."""
        garmin = UserFactory(email="garmin@example.com", first_name="Ada", last_name="Byron")
        whoop = UserFactory(email="whoop@example.com", first_name="Bob", last_name="Ash")
        lonely = UserFactory(email="lonely@example.com", first_name=None, last_name=None)
        UserConnectionFactory(
            user=garmin,
            provider="garmin",
            last_synced_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        UserConnectionFactory(user=whoop, provider="whoop", status=ConnectionStatus.REVOKED)
        return {"garmin": garmin, "whoop": whoop, "lonely": lonely}

    def _ids(self, response: Response) -> set[str]:
        return {item["id"] for item in response.json()["items"]}

    def test_filter_by_provider_matches_any_status(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that the provider filter ignores connection status by default."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?provider=whoop", headers=headers)

        # Assert
        assert response.status_code == 200
        assert self._ids(response) == {str(users["whoop"].id)}
        assert response.json()["total"] == 1

    def test_filter_by_several_providers(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that repeating the provider parameter matches any of them."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?provider=whoop&provider=garmin", headers=headers)

        # Assert
        assert self._ids(response) == {str(users["whoop"].id), str(users["garmin"].id)}

    def test_filter_by_provider_and_connection_status(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that connection_status narrows the provider filter."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?provider=whoop&connection_status=active", headers=headers)

        # Assert
        assert self._ids(response) == set()

    def test_filter_without_active_connection_includes_never_connected(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that has_active_connection=false covers revoked and never-connected users alike."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?has_active_connection=false", headers=headers)

        # Assert
        found = self._ids(response)
        assert {str(users["whoop"].id), str(users["lonely"].id)} <= found
        assert str(users["garmin"].id) not in found

    def test_filter_with_active_connection(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that has_active_connection=true keeps only users with a live connection."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?has_active_connection=true", headers=headers)

        # Assert
        assert self._ids(response) == {str(users["garmin"].id)}

    def test_filter_last_synced_before_includes_never_synced(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that last_synced_before catches idle users and those that never synced."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?last_synced_before=2026-04-01T00:00:00Z", headers=headers)

        # Assert
        assert {str(users["whoop"].id), str(users["lonely"].id)} <= self._ids(response)

    def test_filter_last_synced_before_keeps_recently_synced_users_out(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that a user synced after the cutoff is not reported as idle."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?last_synced_before=2026-02-01T00:00:00Z", headers=headers)

        # Assert
        assert str(users["garmin"].id) not in self._ids(response)

    def test_sort_by_name_puts_unnamed_users_last(
        self, client: TestClient, api_v1_prefix: str, headers: dict, users: dict
    ) -> None:
        """Test that sorting by name orders on first then last name, with unnamed users at the end."""
        # Act
        response = client.get(f"{api_v1_prefix}/users?sort_by=name&sort_order=asc", headers=headers)

        # Assert
        assert response.status_code == 200
        ordered = [item["id"] for item in response.json()["items"]]
        assert ordered.index(str(users["garmin"].id)) < ordered.index(str(users["whoop"].id))
        assert ordered[-1] == str(users["lonely"].id)
