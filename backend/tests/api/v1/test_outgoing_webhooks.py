"""Tests for the outgoing webhooks subsystem.

Covers:
- WebhookEventType enum (#717)
- webhook_emit helpers (#719, #721)
- emit_webhook_event Celery task
- outgoing_webhooks API router (#722-726)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.emit_webhook_event_task import emit_webhook_event
from app.schemas.webhooks.event_types import EVENT_TYPE_DESCRIPTIONS, WebhookEventType
from app.services.outgoing_webhooks.events import (
    _dispatch,
    on_sleep_created,
    on_timeseries_batch_saved,
    on_workout_created,
)
from app.utils.security import create_access_token
from tests.factories import DeveloperFactory

# ---------------------------------------------------------------------------
# WebhookEventType enum
# ---------------------------------------------------------------------------


class TestWebhookEventTypes:
    def test_all_event_types_have_descriptions(self) -> None:
        for evt in WebhookEventType:
            assert evt in EVENT_TYPE_DESCRIPTIONS, f"Missing description for {evt}"

    def test_values_follow_convention(self) -> None:
        for evt in WebhookEventType:
            assert "." in evt.value, f"{evt} should follow resource.action convention"


# ---------------------------------------------------------------------------
# webhook_emit helpers (unit, no Celery/Redis required)
# ---------------------------------------------------------------------------


class TestWebhookEmit:
    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_workout_created_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        rid = uuid4()
        on_workout_created(
            record_id=rid,
            user_id=uid,
            provider="garmin",
            workout_type="RUNNING",
            start_datetime="2026-01-01T00:00:00",
            end_datetime="2026-01-01T01:00:00",
            duration_seconds=3600,
        )
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args
        assert args[0][0] == "workout.created"
        assert args[0][1]["data"]["provider"] == "garmin"

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_sleep_created_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        rid = uuid4()
        on_sleep_created(
            record_id=rid,
            user_id=uid,
            provider="oura",
            start_datetime="2026-01-01T22:00:00",
            end_datetime="2026-01-02T06:00:00",
            duration_seconds=28800,
        )
        mock_task.delay.assert_called_once()
        assert mock_task.delay.call_args[0][0] == "sleep.created"

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_batch_saved_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        on_timeseries_batch_saved(
            user_id=uid,
            provider="garmin",
            series_type="heart_rate",
            sample_count=100,
        )
        mock_task.delay.assert_called_once()
        assert mock_task.delay.call_args[0][0] == "heart_rate.updated"

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_fallback_event_type(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        on_timeseries_batch_saved(
            user_id=uid,
            provider="polar",
            series_type="unknown_type_xyz",
            sample_count=5,
        )
        mock_task.delay.assert_called_once()
        assert mock_task.delay.call_args[0][0] == "timeseries.updated"

    def test_dispatch_swallows_broker_error(self) -> None:
        """_dispatch silently drops the event when Celery is unreachable."""

        with patch(
            "app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event",
        ) as mock_task:
            mock_task.delay.side_effect = ConnectionError("Redis not available")
            # Should NOT raise
            _dispatch("workout.created", {"type": "workout.created", "data": {}})


# ---------------------------------------------------------------------------
# emit_webhook_event Celery task (unit, Svix mocked)
# ---------------------------------------------------------------------------


class TestEmitWebhookEventTask:
    @patch("app.integrations.celery.tasks.emit_webhook_event_task.svix_service")
    @patch("app.integrations.celery.tasks.emit_webhook_event_task.developer_service")
    def test_sends_to_all_developers(
        self,
        mock_dev_service: MagicMock,
        mock_svix: MagicMock,
    ) -> None:
        dev1 = MagicMock(id=uuid4(), email="dev1@test.com")
        dev2 = MagicMock(id=uuid4(), email="dev2@test.com")
        mock_dev_service.crud.get_all.return_value = [dev1, dev2]
        mock_svix.send.return_value = MagicMock(id="msg_123")

        result = emit_webhook_event(
            "workout.created",
            {"type": "workout.created", "data": {}},
        )

        assert result["sent"] == 2
        assert mock_svix.ensure_application.call_count == 2
        assert mock_svix.send.call_count == 2


# ---------------------------------------------------------------------------
# Outgoing webhooks API (#722-726)
# ---------------------------------------------------------------------------


class TestOutgoingWebhooksAPI:
    """Test the /api/v1/webhooks/* endpoints.

    Svix is fully mocked — these are integration tests for the FastAPI
    router, not the Svix server.
    """

    @pytest.fixture(autouse=True)
    def mock_svix(self) -> Any:
        """Mock svix_webhook_service to avoid needing a real Svix server."""
        with patch("app.api.routes.v1.outgoing_webhooks.svix_service") as m:
            m.is_enabled.return_value = True
            m.ensure_application.return_value = "app_uid_123"
            yield m

    def test_list_event_types(self, client: TestClient) -> None:
        resp = client.get("/api/v1/webhooks/event-types")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == len(WebhookEventType)
        names = {e["name"] for e in data}
        assert "workout.created" in names
        assert "sleep.created" in names

    def test_create_endpoint(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        ep_out = MagicMock(id="ep_123", url="https://example.com/wh", description="test", filter_types=None)
        mock_svix.create_endpoint.return_value = ep_out

        resp = client.post(
            "/api/v1/webhooks/endpoints",
            json={"url": "https://example.com/wh", "description": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "ep_123"
        assert data["url"] == "https://example.com/wh"

    def test_list_endpoints(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        list_resp = MagicMock()
        list_resp.data = [
            MagicMock(id="ep_1", url="https://a.com/wh", description="a", filter_types=None),
            MagicMock(id="ep_2", url="https://b.com/wh", description="b", filter_types=["workout.created"]),
        ]
        mock_svix.list_endpoints.return_value = list_resp

        resp = client.get(
            "/api/v1/webhooks/endpoints",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_endpoint(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        resp = client.delete(
            "/api/v1/webhooks/endpoints/ep_123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        mock_svix.delete_endpoint.assert_called_once()

    def test_get_endpoint_secret(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        mock_svix.get_endpoint_secret.return_value = "whsec_test_secret_key"

        resp = client.get(
            "/api/v1/webhooks/endpoints/ep_123/secret",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "whsec_test_secret_key"

    def test_send_test_event(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        mock_svix.send_test_message.return_value = MagicMock(id="msg_test_1")

        resp = client.post(
            "/api/v1/webhooks/endpoints/ep_123/test",
            headers={"Authorization": f"Bearer {token}"},
            json={"event_type": "workout.created"},
        )
        assert resp.status_code == 200
        assert "message_id" in resp.json()

    def test_endpoints_require_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/webhooks/endpoints")
        assert resp.status_code == 401

    def test_svix_disabled_returns_503(
        self,
        client: TestClient,
        db: Session,
        mock_svix: MagicMock,
    ) -> None:
        developer = DeveloperFactory()

        token = create_access_token(developer.id)

        mock_svix.is_enabled.return_value = False

        resp = client.get(
            "/api/v1/webhooks/endpoints",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 503
