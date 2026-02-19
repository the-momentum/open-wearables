"""
Tests for token refresh endpoints.

Tests cover:
- POST /api/v1/token/refresh - exchange refresh token for new access token
- DELETE /api/v1/token/refresh - revoke refresh token
"""

from jose import jwt
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from app.services import refresh_token_service
from _tests.factories import ApplicationFactory, DeveloperFactory, UserFactory


class TestRefreshToken:
    """Tests for POST /api/v1/token/refresh."""

    def test_refresh_sdk_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid SDK refresh token should return new access token and rotated refresh token."""
        # Arrange
        user = UserFactory()
        app_id = "test_app_123"
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, app_id)

        # Act
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        # Refresh token should be rotated (new token returned)
        assert data["refresh_token"] != refresh_token
        assert data["refresh_token"].startswith("rt-")

        # Verify the access token contains correct claims
        payload = jwt.decode(
            data["access_token"], settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False}
        )
        assert payload["sub"] == str(user.id)
        assert payload["scope"] == "sdk"
        assert payload["app_id"] == app_id

    def test_refresh_developer_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid developer refresh token should return new access token and rotated refresh token."""
        # Arrange
        developer = DeveloperFactory()
        refresh_token = refresh_token_service.create_developer_refresh_token(db, developer.id)

        # Act
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        # Refresh token should be rotated (new token returned)
        assert data["refresh_token"] != refresh_token
        assert data["refresh_token"].startswith("rt-")

        # Verify the access token contains developer ID
        payload = jwt.decode(
            data["access_token"], settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False}
        )
        assert payload["sub"] == str(developer.id)
        # Developer tokens don't have scope or app_id
        assert "scope" not in payload or payload.get("scope") is None

    def test_refresh_invalid_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Invalid refresh token should return 401."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": "rt-invalidtoken12345678901234567890"},
        )

        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or revoked refresh token"

    def test_refresh_revoked_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Revoked refresh token should return 401."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")
        refresh_token_service.revoke_token(db, refresh_token)

        # Act
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or revoked refresh token"

    def test_refresh_token_missing_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing refresh_token in body should return validation error."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={},
        )

        # Assert
        assert response.status_code in [400, 422]

    def test_refresh_token_rotation_invalidates_old_token(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """Old refresh token should be invalid after rotation."""
        # Arrange
        user = UserFactory()
        old_refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")

        # Act - refresh once to rotate
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert response.status_code == 200
        new_refresh_token = response.json()["refresh_token"]

        # Assert - old token should be invalid
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert response.status_code == 401

        # Assert - new token should work
        response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": new_refresh_token},
        )
        assert response.status_code == 200


class TestRevokeRefreshToken:
    """Tests for POST /api/v1/token/revoke."""

    def test_revoke_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid refresh token should be revoked successfully."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")

        # Act
        response = client.post(
            f"{api_v1_prefix}/token/revoke",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert response.status_code == 204

        # Verify token is now revoked by trying to refresh
        refresh_response = client.post(
            f"{api_v1_prefix}/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401

    def test_revoke_token_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Non-existent refresh token should return 404."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/token/revoke",
            json={"refresh_token": "rt-nonexistent123456789012345678"},
        )

        # Assert
        assert response.status_code == 404

    def test_revoke_already_revoked_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Already revoked token should return 404."""
        # Arrange
        user = UserFactory()
        refresh_token = refresh_token_service.create_sdk_refresh_token(db, user.id, "test_app")
        refresh_token_service.revoke_token(db, refresh_token)

        # Act
        response = client.post(
            f"{api_v1_prefix}/token/revoke",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert response.status_code == 404


class TestLoginReturnsRefreshToken:
    """Tests that login endpoint returns refresh token."""

    def test_login_returns_refresh_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Login should return both access_token and refresh_token."""
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
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        assert data["refresh_token"].startswith("rt-")


class TestSDKTokenReturnsRefreshToken:
    """Tests that SDK token endpoint returns refresh token (for app credentials)."""

    def test_sdk_token_returns_refresh_token_for_app_credentials(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """SDK token with app credentials should return refresh token."""
        # Arrange
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_app_secret")
        user = UserFactory()  # Create actual user for FK constraint

        # Act
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": application.app_id, "app_secret": "test_app_secret"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        assert data["refresh_token"].startswith("rt-")

    def test_admin_sdk_token_returns_refresh_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Admin-generated SDK token should return refresh token."""
        # Arrange
        from _tests.utils import developer_auth_headers

        developer = DeveloperFactory()
        user = UserFactory()  # Create user
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"].startswith("rt-")
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
