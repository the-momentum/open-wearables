"""
Tests for authentication endpoints.

Tests cover:
- POST /api/v1/auth/login - authentication
- POST /api/v1/auth/logout - session termination
- GET /api/v1/auth/me - current developer info
- PATCH /api/v1/auth/me - update current developer
- GET /api/v1/developers/{developer_id} - get developer by ID
- PATCH /api/v1/developers/{developer_id} - update developer by ID
- DELETE /api/v1/developers/{developer_id} - delete developer
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from tests.factories import DeveloperFactory
from tests.utils import developer_auth_headers


class TestLogin:
    """Tests for POST /api/v1/login."""

    def test_login_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test successful login with valid credentials."""
        # Arrange
        DeveloperFactory(email="test@example.com", password="test123")

        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"username": "test@example.com", "password": "test123"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_login_invalid_password(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test login fails with incorrect password."""
        # Arrange
        DeveloperFactory(email="test@example.com", password="correct_password")

        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"username": "test@example.com", "password": "wrong_password"},
        )

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Incorrect email or password"

    def test_login_nonexistent_user(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test login fails for non-existent user."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"username": "nonexistent@example.com", "password": "anypassword"},
        )

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Incorrect email or password"

    def test_login_missing_username(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test login fails with missing username."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"password": "test123"},
        )

        # Assert
        assert response.status_code in [400, 422]

    def test_login_missing_password(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test login fails with missing password."""
        # Arrange
        DeveloperFactory(email="test@example.com", password="test123")

        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"username": "test@example.com"},
        )

        # Assert
        assert response.status_code in [400, 422]

    def test_login_empty_credentials(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test login fails with empty credentials."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/login",
            data={"username": "", "password": ""},
        )

        # Assert
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/logout."""

    def test_logout_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test successful logout with valid token."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/auth/logout", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"

    def test_logout_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test logout fails without authentication."""
        # Act
        response = client.post(f"{api_v1_prefix}/auth/logout")

        # Assert
        assert response.status_code == 401

    def test_logout_invalid_token(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test logout fails with invalid token."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/auth/logout",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401


class TestGetCurrentDeveloper:
    """Tests for GET /api/v1/me."""

    def test_get_current_developer_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting current developer info with valid authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/auth/me", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(developer.id)
        assert data["email"] == "test@example.com"
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_current_developer_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test getting current developer fails without authentication."""
        # Act
        response = client.get(f"{api_v1_prefix}/auth/me")

        # Assert
        assert response.status_code == 401

    def test_get_current_developer_invalid_token(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test getting current developer fails with invalid token."""
        # Act
        response = client.get(
            f"{api_v1_prefix}/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401


class TestUpdateCurrentDeveloper:
    """Tests for PATCH /api/v1/me."""

    def test_update_current_developer_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating current developer's email."""
        # Arrange
        developer = DeveloperFactory(email="old@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"email": "new@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["id"] == str(developer.id)

        # Verify in database
        db.refresh(developer)
        assert developer.email == "new@example.com"

    def test_update_current_developer_password(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating current developer's password."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="old_password")
        headers = developer_auth_headers(developer.id)
        payload = {"password": "new_password123"}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(developer.id)

        # Verify in database
        db.refresh(developer)
        # Password is updated with the hashed_ prefix pattern from the fixture
        assert developer.hashed_password == "hashed_new_password123"

    def test_update_current_developer_both_fields(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating both email and password."""
        # Arrange
        developer = DeveloperFactory(email="old@example.com", password="old_password")
        headers = developer_auth_headers(developer.id)
        payload = {"email": "new@example.com", "password": "new_password123"}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"

        # Verify in database
        db.refresh(developer)
        assert developer.email == "new@example.com"
        # Password is updated with the hashed_ prefix pattern from the fixture
        assert developer.hashed_password == "hashed_new_password123"

    def test_update_current_developer_empty_payload(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating with empty payload."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_update_current_developer_invalid_email(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating with invalid email format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"email": "not-an-email"}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code in [400, 422]

    def test_update_current_developer_short_password(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating with password that's too short."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"password": "short"}

        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json=payload, headers=headers)

        # Assert
        assert response.status_code in [400, 422]

    def test_update_current_developer_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test updating current developer fails without authentication."""
        # Act
        response = client.patch(f"{api_v1_prefix}/auth/me", json={"email": "new@example.com"})

        # Assert
        assert response.status_code == 401


class TestGetDeveloperById:
    """Tests for GET /api/v1/developers/{developer_id}."""

    def test_get_developer_by_id_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting developer by ID with valid authentication."""
        # Arrange
        auth_developer = DeveloperFactory(email="auth@example.com", password="test123")
        target_developer = DeveloperFactory(email="target@example.com", password="test123")
        headers = developer_auth_headers(auth_developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developers/{target_developer.id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(target_developer.id)
        assert data["email"] == "target@example.com"

    def test_get_developer_by_id_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting non-existent developer raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.get(f"{api_v1_prefix}/developers/{fake_id}", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_get_developer_by_id_invalid_uuid(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting developer with invalid UUID format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developers/not-a-uuid", headers=headers)

        # Assert
        assert response.status_code in [400, 422]

    def test_get_developer_by_id_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test getting developer by ID fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")

        # Act
        response = client.get(f"{api_v1_prefix}/developers/{developer.id}")

        # Assert
        assert response.status_code == 401


class TestUpdateDeveloperById:
    """Tests for PATCH /api/v1/developers/{developer_id}."""

    def test_update_developer_by_id_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating developer by ID."""
        # Arrange
        auth_developer = DeveloperFactory(email="auth@example.com", password="test123")
        target_developer = DeveloperFactory(email="target@example.com", password="test123")
        headers = developer_auth_headers(auth_developer.id)
        payload = {"email": "updated@example.com"}

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developers/{target_developer.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"

        # Verify in database
        db.refresh(target_developer)
        assert target_developer.email == "updated@example.com"

    def test_update_developer_by_id_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating non-existent developer raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_id = "00000000-0000-0000-0000-000000000000"
        payload = {"email": "updated@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/developers/{fake_id}", json=payload, headers=headers)

        # Assert
        assert response.status_code == 404

    def test_update_developer_by_id_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating developer by ID fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        payload = {"email": "updated@example.com"}

        # Act
        response = client.patch(f"{api_v1_prefix}/developers/{developer.id}", json=payload)

        # Assert
        assert response.status_code == 401

    def test_update_developer_by_id_invalid_data(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating developer with invalid data."""
        # Arrange
        auth_developer = DeveloperFactory(email="auth@example.com", password="test123")
        target_developer = DeveloperFactory(email="target@example.com", password="test123")
        headers = developer_auth_headers(auth_developer.id)
        payload = {"email": "not-an-email", "password": "short"}

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developers/{target_developer.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code in [400, 422]


class TestDeleteDeveloperById:
    """Tests for DELETE /api/v1/developers/{developer_id}."""

    def test_delete_developer_by_id_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting developer by ID."""
        # Arrange
        auth_developer = DeveloperFactory(email="auth@example.com", password="test123")
        target_developer = DeveloperFactory(email="target@example.com", password="test123")
        headers = developer_auth_headers(auth_developer.id)
        target_id = target_developer.id

        # Act
        response = client.delete(f"{api_v1_prefix}/developers/{target_id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(target_id)
        assert data["email"] == "target@example.com"

        # Verify developer is deleted from database
        from app.services import developer_service

        deleted_developer = developer_service.get(db, target_id, raise_404=False)
        assert deleted_developer is None

    def test_delete_developer_by_id_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting non-existent developer raises ResourceNotFoundError."""

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.delete(f"{api_v1_prefix}/developers/{fake_id}", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_delete_developer_by_id_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting developer fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")

        # Act
        response = client.delete(f"{api_v1_prefix}/developers/{developer.id}")

        # Assert
        assert response.status_code == 401

    def test_delete_developer_by_id_invalid_uuid(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting developer with invalid UUID format."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/developers/not-a-uuid", headers=headers)

        # Assert
        assert response.status_code in [400, 422]
