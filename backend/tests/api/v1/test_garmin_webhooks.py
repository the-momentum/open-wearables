"""Tests for Garmin webhook HTTP contract layer.

The /api/v1/providers/garmin/webhooks endpoint immediately returns
{"status": "accepted"} and enqueues all processing to the process_push
Celery task. Processing logic is tested in tests/tasks/test_garmin_webhook_task.py.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PUSH_ENDPOINT = "/api/v1/providers/garmin/webhooks"
LEGACY_PUSH_ENDPOINT = "/api/v1/garmin/webhooks/push"
LEGACY_PING_ENDPOINT = "/api/v1/garmin/webhooks/ping"
WEBHOOK_HANDLER = "app.services.providers.garmin.webhook_handler"
PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"


class TestGarminWebhookAuth:
    """Authentication checks for the webhook endpoint."""

    def test_missing_client_id_returns_401(self, client: TestClient, db: Session) -> None:
        """Requests without garmin-client-id header must be rejected."""
        response = client.post(PUSH_ENDPOINT, json={"activities": []})
        assert response.status_code == 401

    def test_valid_client_id_returns_accepted(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Valid request returns 200 with {"status": "accepted"} immediately."""
        headers = {"garmin-client-id": "test-client-id"}
        response = client.post(PUSH_ENDPOINT, headers=headers, json={"activities": []})

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_invalid_json_returns_400(self, client: TestClient, db: Session) -> None:
        """Malformed JSON body returns 400."""
        response = client.post(
            PUSH_ENDPOINT,
            content=b"not json",
            headers={"garmin-client-id": "test-client-id", "Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestGarminWebhookTaskEnqueue:
    """Verify that dispatch() enqueues the process_push Celery task."""

    def test_enqueues_process_push_task(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """POST enqueues process_push with the raw payload."""
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345,
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
                },
            ],
        }
        headers = {"garmin-client-id": "test-client-id"}

        with patch(f"{WEBHOOK_HANDLER}.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="test-task-id")
            response = client.post(PUSH_ENDPOINT, headers=headers, json=payload)

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        mock_celery.send_task.assert_called_once()
        task_name, _ = mock_celery.send_task.call_args[0][0], mock_celery.send_task.call_args
        assert task_name == PROCESS_PUSH_TASK

    def test_enqueues_task_with_correct_payload(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """The payload passed to send_task matches the incoming webhook body."""
        payload = {"hrv": [{"userId": "u1", "summaryId": "s1"}]}
        headers = {"garmin-client-id": "test-client-id"}

        with patch(f"{WEBHOOK_HANDLER}.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-xyz")
            client.post(PUSH_ENDPOINT, headers=headers, json=payload)

        # send_task(_PROCESS_PUSH_TASK, args=["garmin", payload, trace_id])
        sent_args = mock_celery.send_task.call_args[1]["args"]
        assert sent_args[0] == "garmin"
        assert sent_args[1] == payload


class TestGarminWebhookRouting:
    """Routing and method checks for the unified provider webhook router."""

    def test_get_challenge_returns_501(self, client: TestClient, db: Session) -> None:
        """Garmin does not support GET subscription challenges — expect 501."""
        response = client.get(PUSH_ENDPOINT)
        assert response.status_code == 501

    def test_unknown_provider_returns_404(self, client: TestClient, db: Session) -> None:
        """Unknown provider names return 404."""
        response = client.post(
            "/api/v1/providers/unknown_provider/webhooks",
            headers={"garmin-client-id": "x"},
            json={},
        )
        assert response.status_code == 404


class TestGarminDeprecatedRoutes:
    """Legacy /garmin/webhooks/* routes must still return {"status": "accepted"}."""

    def test_legacy_push_route_returns_accepted(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Deprecated /api/v1/garmin/webhooks/push delegates to the same handler."""
        headers = {"garmin-client-id": "test-client-id"}
        response = client.post(LEGACY_PUSH_ENDPOINT, headers=headers, json={"activities": []})

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}

    def test_legacy_ping_route_returns_accepted(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Deprecated /api/v1/garmin/webhooks/ping also delegates to the handler."""
        headers = {"garmin-client-id": "test-client-id"}
        response = client.post(LEGACY_PING_ENDPOINT, headers=headers, json={"activities": []})

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
