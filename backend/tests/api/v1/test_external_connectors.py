"""Tests for external connectors endpoints authentication."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.services.sdk_token_service import create_sdk_user_token
from tests.factories import ApiKeyFactory


@pytest.fixture(autouse=True)
def mock_celery_tasks() -> Generator[MagicMock, None, None]:
    """Mock Celery tasks to prevent actual task execution during tests."""
    with patch("app.api.routes.v1.external_connectors.process_apple_upload") as mock:
        mock.delay.return_value = None
        yield mock


class TestExternalConnectorsAuth:
    """Tests for external connectors endpoints authentication."""

    def test_auto_health_export_accepts_sdk_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """SDK token should be accepted for auto-health-export sync."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_sdk_user_token("app_123", user_id)

        response = client.post(
            f"{api_v1_prefix}/users/{user_id}/import/apple/auto-health-export",
            headers={"Authorization": f"Bearer {token}"},
            json={"data": {"workouts": []}},
        )

        # Should not be 401
        assert response.status_code != 401

    def test_auto_health_export_still_accepts_api_key(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """API key should still work for auto-health-export."""
        api_key = ApiKeyFactory()

        response = client.post(
            f"{api_v1_prefix}/users/user_456/import/apple/auto-health-export",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            json={"data": {"workouts": []}},
        )

        # Should not be 401
        assert response.status_code != 401

    def test_auto_health_export_no_auth_returns_401(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """No authentication should return 401 for auto-health-export."""
        response = client.post(
            f"{api_v1_prefix}/users/user_456/import/apple/auto-health-export",
            json={"data": {"workouts": []}},
        )

        assert response.status_code == 401
