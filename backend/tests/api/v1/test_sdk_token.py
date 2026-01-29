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
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": application.app_id, "app_secret": "test_app_secret"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_create_token_invalid_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Non-existent app_id should return 401."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": "nonexistent", "app_secret": "secret"},
        )
        assert response.status_code == 401

    def test_create_token_invalid_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Wrong app_secret should return 401."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="real_secret")
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": application.app_id, "app_secret": "wrong_secret"},
        )
        assert response.status_code == 401

    def test_token_contains_correct_claims(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Token should contain scope=sdk, sub=user_id, app_id."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_secret")
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": application.app_id, "app_secret": "test_secret"},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False})

        assert payload["sub"] == user_id
        assert payload["scope"] == "sdk"
        assert payload["app_id"] == application.app_id
        # NOTE: infinite=True is hardcoded in the endpoint for now, so no exp claim is expected.
        # If this changes back to default expiration, this test needs to check for 'exp'.
        assert "exp" not in payload

    def test_token_without_exp_when_infinite(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Token with infinite=true should not contain exp claim."""
        developer = DeveloperFactory()
        application = ApplicationFactory(developer=developer, app_secret="test_secret")
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": application.app_id, "app_secret": "test_secret", "infinite": True},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]
        # Decode without exp verification since it has no exp
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False})

        assert payload["sub"] == user_id
        assert payload["scope"] == "sdk"
        assert payload["app_id"] == application.app_id
        assert "exp" not in payload

    def test_create_token_missing_app_id(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_id should return validation error."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_secret": "secret"},
        )
        # FastAPI returns 422 for validation errors, but some configs return 400
        assert response.status_code in [400, 422]

    def test_create_token_missing_app_secret(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Missing app_secret should return validation error."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/token",
            json={"app_id": "app_123"},
        )
        assert response.status_code in [400, 422]

    def test_create_token_empty_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Empty body should return validation error."""
        response = client.post(
            f"{api_v1_prefix}/users/user123/token",
            json={},
        )
        assert response.status_code in [400, 422]
