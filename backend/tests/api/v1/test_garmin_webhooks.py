"""
Tests for Garmin webhook endpoints (HTTP contract layer).

The endpoints immediately return 200 {"status": "accepted"} and delegate
all processing to Celery background tasks. These tests verify:
- Authentication (garmin-client-id header required)
- Correct HTTP response shape
- Background task is enqueued with the right payload
- Health check endpoint

Processing logic (DB updates, activity saving, permissions, deregistrations)
is tested separately in tests/tasks/test_garmin_webhook_task.py.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestGarminPingWebhook:
    """Test suite for Garmin ping webhook endpoint."""

    def test_ping_missing_client_id_returns_401(self, client: TestClient) -> None:
        """Ping webhook requires garmin-client-id header."""
        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            json={"activities": [{"userId": "garmin_user_123", "callbackURL": "https://example.com/callback"}]},
        )

        # Assert
        assert response.status_code == 401

    def test_ping_valid_payload_returns_accepted(self, client: TestClient) -> None:
        """Valid ping request returns 200 with status=accepted immediately."""
        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_ping") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-abc")

            response = client.post(
                "/api/v1/garmin/webhooks/ping",
                headers={"garmin-client-id": "test-client-id"},
                json={"activities": [{"userId": "garmin_user_123", "callbackURL": "https://example.com/callback"}]},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_ping_enqueues_task_with_payload(self, client: TestClient) -> None:
        """Ping endpoint enqueues a Celery task with the exact received payload."""
        payload = {
            "activities": [{"userId": "garmin_user_123", "callbackURL": "https://example.com/callback"}],
            "dailies": [{"userId": "garmin_user_123"}],
        }

        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_ping") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-abc")

            client.post(
                "/api/v1/garmin/webhooks/ping",
                headers={"garmin-client-id": "test-client-id"},
                json=payload,
            )

            mock_task.delay.assert_called_once()
            call_payload = mock_task.delay.call_args[0][0]
            assert call_payload == payload

    def test_ping_with_multiple_summary_types(self, client: TestClient) -> None:
        """Ping with mixed payload types returns 200 without error."""
        payload = {
            "activities": [],
            "activityDetails": [{"userId": "garmin_user_123"}],
            "dailies": [{"userId": "garmin_user_123"}],
            "sleeps": [{"userId": "garmin_user_123"}],
        }

        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_ping") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-abc")

            response = client.post(
                "/api/v1/garmin/webhooks/ping",
                headers={"garmin-client-id": "test-client-id"},
                json=payload,
            )

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_ping_returns_500_when_task_dispatch_fails(self, client: TestClient) -> None:
        """Ping webhook returns 500 if the background task cannot be enqueued."""
        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_ping") as mock_task:
            mock_task.delay.side_effect = Exception("Celery broker unavailable")

            response = client.post(
                "/api/v1/garmin/webhooks/ping",
                headers={"garmin-client-id": "test-client-id"},
                json={"activities": [{"userId": "garmin_user_123", "callbackURL": "https://example.com/cb"}]},
            )

        assert response.status_code == 500


class TestGarminPushWebhook:
    """Test suite for Garmin push webhook endpoint."""

    def test_push_missing_client_id_returns_401(self, client: TestClient, db: Session) -> None:
        """Push webhook requires garmin-client-id header."""
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            json={
                "activities": [
                    {
                        "userId": "garmin_user_123",
                        "activityId": 12345,
                        "activityName": "Test Activity",
                        "activityType": "RUNNING",
                        "startTimeInSeconds": 1763597760,
                        "durationInSeconds": 3600,
                    }
                ]
            },
        )
        assert response.status_code == 401

    def test_push_valid_payload_returns_accepted(self, client: TestClient, db: Session) -> None:
        """Valid push request returns 200 with status=accepted immediately."""
        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_push") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-xyz")

            response = client.post(
                "/api/v1/garmin/webhooks/push",
                headers={"garmin-client-id": "test-client-id"},
                json={
                    "activities": [
                        {
                            "userId": "garmin_user_123",
                            "activityId": 12345,
                            "activityName": "Morning Run",
                            "activityType": "RUNNING",
                            "startTimeInSeconds": 1763597760,
                            "durationInSeconds": 3600,
                        }
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_push_enqueues_task_with_payload(self, client: TestClient, db: Session) -> None:
        """Push endpoint enqueues a Celery task with the exact received payload."""
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345,
                    "activityName": "Morning Run",
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
                }
            ],
            "dailies": [{"userId": "garmin_user_123"}],
        }

        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_push") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-xyz")

            client.post(
                "/api/v1/garmin/webhooks/push",
                headers={"garmin-client-id": "test-client-id"},
                json=payload,
            )

            mock_task.delay.assert_called_once()
            call_payload = mock_task.delay.call_args[0][0]
            assert call_payload == payload

    def test_push_returns_500_when_task_dispatch_fails(self, client: TestClient, db: Session) -> None:
        """Push webhook returns 500 if the background task cannot be enqueued."""
        with patch("app.api.routes.v1.garmin_webhooks.process_garmin_push") as mock_task:
            mock_task.delay.side_effect = Exception("Celery broker unavailable")

            response = client.post(
                "/api/v1/garmin/webhooks/push",
                headers={"garmin-client-id": "test-client-id"},
                json={
                    "activities": [
                        {
                            "userId": "garmin_user_123",
                            "activityId": 12345,
                            "activityType": "RUNNING",
                            "startTimeInSeconds": 1763597760,
                            "durationInSeconds": 3600,
                        }
                    ]
                },
            )

        assert response.status_code == 500


class TestGarminWebhookHealth:
    """Test suite for Garmin webhook health check endpoint."""

    def test_health_check_success(self, client: TestClient, db: Session) -> None:
        """Test that health check returns OK."""
        # Act
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "garmin-webhooks"

    def test_health_check_no_auth_required(self, client: TestClient, db: Session) -> None:
        """Test that health check doesn't require authentication."""
        # Act - no headers
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200

    def test_health_check_response_structure(self, client: TestClient, db: Session) -> None:
        """Test health check response structure."""
        # Act
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert "service" in data
