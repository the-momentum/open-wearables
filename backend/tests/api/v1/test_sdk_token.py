"""Tests for SDK token exchange endpoint."""

from dirty_equals import IsInt, IsStr
from jose import jwt
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from tests.factories import ApplicationFactory, DeveloperFactory, UserFactory


class TestCreateUserToken:
    """Tests for POST /api/v1/users/{external_user_id}/token"""

    def test_create_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid app credentials should return JWT token with refresh token."""
        developer = DeveloperFactory()
        # Create application with known secret
        application = ApplicationFactory(developer=developer, app_secret="test_app_secret")
        user = UserFactory()  # Create real user for FK constraint

        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": application.app_id, "app_secret": "test_app_secret"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "access_token": IsStr,
            "refresh_token": IsStr(regex=r"rt-.*"),
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "password_change": None,
        }

    def test_create_token_invalid_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Non-existent app_id should return 401."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": "nonexistent", "app_secret": "secret"},
        )
        assert response.status_code == 401

    def test_create_token_invalid_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Wrong app_secret should return 401."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="real_secret")
        user = UserFactory()

        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": application.app_id, "app_secret": "wrong_secret"},
        )
        assert response.status_code == 401

    def test_token_contains_correct_claims(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Token should contain scope=sdk, sub=user_id, app_id."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_secret")
        user = UserFactory()

        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": application.app_id, "app_secret": "test_secret"},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False})

        assert payload == {
            "sub": str(user.id),
            "scope": "sdk",
            "app_id": application.app_id,
            "exp": IsInt,
        }

    def test_create_token_missing_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_id is a 400: both fields are optional, the route needs the pair."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_secret": "secret"},
        )
        assert response.status_code == 400

    def test_create_token_missing_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_secret is a 400: both fields are optional, the route needs the pair."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": "app_123"},
        )
        assert response.status_code == 400

    def test_create_token_empty_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Empty body is a 400: neither credentials nor a Bearer token."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={},
        )
        assert response.status_code == 400
