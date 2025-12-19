"""Tests for SDK token exchange endpoint."""

from jose import jwt
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from tests.factories import ApplicationFactory, DeveloperFactory


class TestCreateUserToken:
    """Tests for POST /api/v1/users/{external_user_id}/token"""

    def test_create_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid app credentials should return JWT token."""
        developer = DeveloperFactory()
        # Create application with known secret (factory uses "hashed_test_app_secret" as hash)
        application = ApplicationFactory(developer=developer, app_secret="test_app_secret")

        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={"app_id": application.app_id, "app_secret": "test_app_secret"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_create_token_invalid_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Non-existent app_id should return 401."""
        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={"app_id": "nonexistent", "app_secret": "secret"},
        )
        assert response.status_code == 401

    def test_create_token_invalid_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Wrong app_secret should return 401."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="real_secret")

        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={"app_id": application.app_id, "app_secret": "wrong_secret"},
        )
        assert response.status_code == 401

    def test_token_contains_correct_claims(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Token should contain scope=sdk, sub=external_user_id, app_id."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_secret")

        response = client.post(
            f"{api_v1_prefix}/users/my_user_123/token",
            json={"app_id": application.app_id, "app_secret": "test_secret"},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload["sub"] == "my_user_123"
        assert payload["scope"] == "sdk"
        assert payload["app_id"] == application.app_id
        assert "exp" in payload

    def test_create_token_missing_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_id should return 422."""
        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={"app_secret": "secret"},
        )
        assert response.status_code == 422

    def test_create_token_missing_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_secret should return 422."""
        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={"app_id": "app_123"},
        )
        assert response.status_code == 422

    def test_create_token_empty_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Empty body should return 422."""
        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={},
        )
        assert response.status_code == 422
