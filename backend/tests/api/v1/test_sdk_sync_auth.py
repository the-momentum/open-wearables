"""Tests for SDK sync endpoints authentication."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import ApiKeyFactory, DeveloperFactory
from tests.utils import developer_auth_headers


@pytest.fixture(autouse=True)
def mock_celery_tasks() -> Generator[MagicMock, None, None]:
    """Mock Celery tasks to prevent actual task execution during tests."""
    with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock:
        mock.delay.return_value = None
        yield mock


class TestSDKSyncWithSDKToken:
    """Tests for SDK sync endpoints with SDK token authentication."""

    def test_apple_health_sdk_endpoint_accepts_sdk_token(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """SDK token should be accepted for apple-health-sdk sync."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_sdk_user_token("app_123", user_id)

        response = client.post(
            f"{api_v1_prefix}/sdk/users/{user_id}/sync/apple",
            headers={"Authorization": f"Bearer {token}"},
            json={"data": {"workouts": [], "records": []}},
        )

        # Should not be 401 (auth should pass)
        # May be 400/422 if data format is wrong, but auth should pass
        assert response.status_code != 401

    def test_apple_health_sdk_still_accepts_api_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """API key should still work for apple-health-sdk (backwards compatibility)."""
        api_key = ApiKeyFactory()
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        response = client.post(
            f"{api_v1_prefix}/sdk/users/{user_id}/sync/apple",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json={"data": {"workouts": [], "records": []}},
        )

        # Should not be 401
        assert response.status_code != 401

    def test_no_auth_returns_401(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """No authentication should return 401."""
        response = client.post(
            f"{api_v1_prefix}/sdk/users/user_456/sync/apple",
            json={"data": {"workouts": [], "records": []}},
        )

        assert response.status_code == 401


class TestSDKTokenBlockedElsewhere:
    """Tests for SDK tokens being rejected on non-SDK endpoints."""

    def test_sdk_token_rejected_on_auth_me(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be rejected on /auth/me."""
        token = create_sdk_user_token("app_123", "user_456")

        response = client.get(
            f"{api_v1_prefix}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_sdk_token_rejected_on_dashboard(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be rejected on dashboard endpoints."""
        token = create_sdk_user_token("app_123", "user_456")

        response = client.get(
            f"{api_v1_prefix}/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_sdk_token_rejected_on_applications(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be rejected on applications endpoints."""
        token = create_sdk_user_token("app_123", "user_456")

        response = client.get(
            f"{api_v1_prefix}/applications",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_sdk_token_rejected_on_api_keys(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be rejected on API keys endpoints."""
        token = create_sdk_user_token("app_123", "user_456")

        response = client.get(
            f"{api_v1_prefix}/developer/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_sdk_token_rejected_on_users_list(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be rejected on users list endpoint."""
        token = create_sdk_user_token("app_123", "user_456")

        response = client.get(
            f"{api_v1_prefix}/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_developer_token_still_works_on_auth_me(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Developer token should still work on /auth/me."""
        developer = DeveloperFactory()
        headers = developer_auth_headers(developer.id)

        response = client.get(
            f"{api_v1_prefix}/auth/me",
            headers=headers,
        )

        assert response.status_code == 200
