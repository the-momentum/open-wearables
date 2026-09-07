"""Tests for SDK token exchange endpoint."""

from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.config import settings
from app.models import RefreshToken
from tests.factories import ApplicationFactory, DeveloperFactory, UserFactory
from tests.utils import developer_auth_headers


class TestCreateUserToken:
    """Tests for POST /api/v1/users/{external_user_id}/token"""

    def test_create_token_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Valid app credentials should return JWT token with refresh token."""
        developer = DeveloperFactory()
        # Create application with known secret (factory uses "hashed_test_app_secret" as hash)
        application = ApplicationFactory(developer=developer, app_secret="test_app_secret")
        user = UserFactory()  # Create real user for FK constraint

        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": application.app_id, "app_secret": "test_app_secret"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        assert data["refresh_token"].startswith("rt-")

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

        assert payload["sub"] == str(user.id)
        assert payload["scope"] == "sdk"
        assert payload["app_id"] == application.app_id
        assert "exp" in payload

    def test_create_token_missing_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_id should return validation error."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_secret": "secret"},
        )
        # FastAPI returns 422 for validation errors, but some configs return 400
        assert response.status_code in [400, 422]

    def test_create_token_missing_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_secret should return validation error."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={"app_id": "app_123"},
        )
        assert response.status_code in [400, 422]

    def test_create_token_empty_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Empty body should return validation error."""
        user = UserFactory()
        response = client.post(
            f"{api_v1_prefix}/users/{user.id}/token",
            json={},
        )
        assert response.status_code in [400, 422]

    @pytest.mark.parametrize("auth_method", ["application", "admin"])
    def test_missing_user_does_not_issue_tokens(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
        auth_method: str,
    ) -> None:
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_secret")
        missing_user = uuid4()
        before = db.query(RefreshToken).count()
        response = client.post(
            f"{api_v1_prefix}/users/{missing_user}/token",
            json={"app_id": application.app_id, "app_secret": "test_secret"} if auth_method == "application" else None,
            headers=developer_auth_headers(developer.id) if auth_method == "admin" else {},
        )
        assert response.status_code == 404
        assert "access_token" not in response.json()
        assert db.query(RefreshToken).count() == before

    def test_missing_user_with_invalid_credentials_still_returns_401(
        self,
        client: TestClient,
        db: Session,
        api_v1_prefix: str,
    ) -> None:
        application = ApplicationFactory(app_secret="real_secret")
        response = client.post(
            f"{api_v1_prefix}/users/{uuid4()}/token",
            json={"app_id": application.app_id, "app_secret": "wrong_secret"},
        )
        assert response.status_code == 401
        assert db.query(RefreshToken).count() == 0
