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
    SVIX_MAX_SAMPLES_PER_EVENT,
    _dispatch,
    on_connection_created,
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
            device="Forerunner 255",
            workout_type="RUNNING",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T01:00:00",
            zone_offset="+01:00",
            duration_seconds=3600,
            calories_kcal=450.0,
            distance_meters=10000.0,
            avg_heart_rate_bpm=155,
            max_heart_rate_bpm=178,
            elevation_gain_meters=120.0,
            avg_pace_sec_per_km=360,
        )
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args
        assert args[0][0] == "workout.created"
        assert args[0][1]["data"]["source"]["provider"] == "garmin"
        assert args[0][1]["data"]["calories_kcal"] == 450.0
        assert args[0][1]["data"]["distance_meters"] == 10000.0
        assert args[0][1]["data"]["avg_heart_rate_bpm"] == 155

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_sleep_created_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        rid = uuid4()
        on_sleep_created(
            record_id=rid,
            user_id=uid,
            provider="oura",
            device="Oura Ring Gen3",
            start_time="2026-01-01T22:00:00",
            end_time="2026-01-02T06:00:00",
            zone_offset=None,
            duration_seconds=28800,
            efficiency_percent=85.0,
            stages={"deep_minutes": 90, "rem_minutes": 60, "light_minutes": 120, "awake_minutes": 10},
            is_nap=False,
        )
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args
        assert args[0][0] == "sleep.created"
        assert args[0][1]["data"]["efficiency_percent"] == 85.0
        assert args[0][1]["data"]["stages"]["deep_minutes"] == 90

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_batch_saved_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        samples = [
            {
                "timestamp": "2026-04-16T06:00:00+00:00",
                "zone_offset": "+00:00",
                "type": "heart_rate",
                "value": 62.0,
                "unit": "bpm",
                "source": {"provider": "garmin", "device": "Forerunner 255"},
            },
            {
                "timestamp": "2026-04-16T06:05:00+00:00",
                "zone_offset": "+00:00",
                "type": "heart_rate",
                "value": 65.0,
                "unit": "bpm",
                "source": {"provider": "garmin", "device": "Forerunner 255"},
            },
        ]
        on_timeseries_batch_saved(
            user_id=uid,
            provider="garmin",
            series_type="heart_rate",
            sample_count=2,
            start_time="2026-04-16T06:00:00+00:00",
            end_time="2026-04-16T06:05:00+00:00",
            samples=samples,
        )
        mock_task.delay.assert_called()
        assert mock_task.delay.call_count == 2
        calls = {c[0][0] for c in mock_task.delay.call_args_list}
        assert "heart_rate.created" in calls
        assert "series.heart_rate.created" in calls
        # validate payload on the group event
        group_call = next(c for c in mock_task.delay.call_args_list if c[0][0] == "heart_rate.created")
        args = group_call
        data = args[0][1]["data"]
        assert data["start_time"] == "2026-04-16T06:00:00+00:00"
        assert data["end_time"] == "2026-04-16T06:05:00+00:00"
        assert len(data["samples"]) == 2
        assert data["samples"][0]["value"] == 62.0
        assert data["samples"][1]["value"] == 65.0
        assert "chunk_index" not in data

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_batch_saved_without_samples(self, mock_task: MagicMock) -> None:
        """Backward-compatible call without samples still dispatches correctly."""
        uid = uuid4()
        on_timeseries_batch_saved(
            user_id=uid,
            provider="garmin",
            series_type="heart_rate",
            sample_count=100,
        )
        assert mock_task.delay.call_count == 2
        calls = {c[0][0] for c in mock_task.delay.call_args_list}
        assert "heart_rate.created" in calls
        assert "series.heart_rate.created" in calls
        group_call = next(c for c in mock_task.delay.call_args_list if c[0][0] == "heart_rate.created")
        data = group_call[0][1]["data"]
        assert data["samples"] == []
        assert data["sample_count"] == 100

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_batch_saved_chunks_large_payload(self, mock_task: MagicMock) -> None:
        """Batches exceeding SVIX_MAX_SAMPLES_PER_EVENT are split into chunk events."""
        uid = uuid4()
        large_samples = [
            {
                "timestamp": f"2026-04-16T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}+00:00",
                "zone_offset": "+00:00",
                "type": "heart_rate",
                "value": float(60 + i % 40),
                "unit": "bpm",
                "source": {"provider": "garmin", "device": None},
            }
            for i in range(SVIX_MAX_SAMPLES_PER_EVENT + 10)
        ]
        on_timeseries_batch_saved(
            user_id=uid,
            provider="garmin",
            series_type="heart_rate",
            sample_count=len(large_samples),
            start_time=large_samples[0]["timestamp"],
            end_time=large_samples[-1]["timestamp"],
            samples=large_samples,
        )
        # 2 chunks × 2 event types (group + granular) = 4 calls
        assert mock_task.delay.call_count == 4
        group_calls = [c for c in mock_task.delay.call_args_list if c[0][0] == "heart_rate.created"]
        assert len(group_calls) == 2
        first_data = group_calls[0][0][1]["data"]
        second_data = group_calls[1][0][1]["data"]
        assert first_data["chunk_index"] == 0
        assert first_data["total_chunks"] == 2
        assert second_data["chunk_index"] == 1
        assert second_data["total_chunks"] == 2
        assert len(first_data["samples"]) == SVIX_MAX_SAMPLES_PER_EVENT
        assert len(second_data["samples"]) == 10
        # sample_count reflects the full batch in every chunk
        assert first_data["sample_count"] == len(large_samples)
        assert second_data["sample_count"] == len(large_samples)

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_timeseries_skips_unmapped_series_type(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        on_timeseries_batch_saved(
            user_id=uid,
            provider="polar",
            series_type="unknown_type_xyz",
            sample_count=5,
        )
        mock_task.delay.assert_not_called()

    @patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event")
    def test_on_connection_created_dispatches(self, mock_task: MagicMock) -> None:
        uid = uuid4()
        cid = uuid4()
        on_connection_created(
            user_id=uid,
            provider="garmin",
            connection_id=cid,
            connected_at="2026-01-01T12:00:00+00:00",
        )
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args
        assert args[0][0] == "connection.created"
        assert args[0][1]["data"]["provider"] == "garmin"
        assert args[0][1]["data"]["connection_id"] == str(cid)

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
            m.user_id_from_endpoint.return_value = None
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
