"""Tests for the anonymous usage telemetry service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ProviderSetting
from app.schemas.auth import ConnectionStatus, LiveSyncMode
from app.services.telemetry_service import telemetry_service
from tests.factories import DataSourceFactory, EventRecordFactory, UserConnectionFactory, UserFactory

FEATURE_KEYS = {
    "sentry_enabled",
    "ingest_workout_samples",
    "store_fit_files",
    "historical_sync_on_connect",
    "raw_payload_storage",
    "outgoing_webhooks_enabled",
    "default_data_granularity",
}


class TestTelemetryState:
    def test_get_or_create_state_creates_stable_singleton(self, db: Session) -> None:
        first = telemetry_service.get_or_create_state(db)
        second = telemetry_service.get_or_create_state(db)

        assert first.id == 1
        assert second.id == 1
        assert first.instance_id == second.instance_id
        assert first.created_at is not None
        assert first.last_sent_at is None


class TestBuildPayload:
    def test_payload_shape_and_counts(self, db: Session) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        UserConnectionFactory(user=user_a, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user_b, provider="oura", status=ConnectionStatus.REVOKED)
        db.add(
            ProviderSetting(
                provider="garmin",
                is_enabled=True,
                live_sync_mode=LiveSyncMode.WEBHOOK,
                webhook_secret=None,
                data_granularity=None,
            )
        )
        db.flush()

        payload = telemetry_service.build_payload(db, event="daily")

        assert payload["schema_version"] == 2
        assert payload["event"] == "daily"
        assert len(payload["instance_id"]) == 32
        assert payload["app_version"]
        assert payload["environment"]
        assert payload["sent_at"]
        assert payload["total_users"] == 2
        assert payload["active_connections"] == 1
        assert payload["inactive_connections"] == 1
        assert payload["users_with_active_connection"] == 1
        assert payload["connections_by_provider"] == {"garmin": 1}

        garmin = next(p for p in payload["providers"] if p["provider"] == "garmin")
        assert garmin["is_enabled"] is True
        assert garmin["live_sync_mode"] == "webhook"

        assert set(payload["features"]) == FEATURE_KEYS

    def test_event_counts_are_split_by_category(self, db: Session) -> None:
        garmin_source = DataSourceFactory(provider="garmin")
        oura_source = DataSourceFactory(provider="oura")
        EventRecordFactory(data_source=garmin_source, category="workout")
        EventRecordFactory(data_source=garmin_source, category="sleep")
        EventRecordFactory(data_source=oura_source, category="sleep")
        EventRecordFactory(data_source=oura_source, category="menstrual_cycle")
        db.flush()

        payload = telemetry_service.build_payload(db, event="daily")

        assert payload["workouts_by_provider"] == {"garmin": 1}
        assert payload["sleep_sessions_by_provider"] == {"garmin": 1, "oura": 1}
        assert payload["menstrual_cycles_by_provider"] == {"oura": 1}

    def test_payload_is_json_serializable_and_contains_no_pii(self, db: Session) -> None:
        user = UserFactory(email="jane.doe@example.com", first_name="Jane", last_name="Doe")
        UserConnectionFactory(user=user, provider="garmin", provider_username="jane_doe_92")

        serialized = json.dumps(telemetry_service.build_payload(db, event="startup"))

        assert "jane.doe@example.com" not in serialized
        assert "Jane" not in serialized
        assert "Doe" not in serialized
        assert "jane_doe_92" not in serialized
        assert settings.secret_key not in serialized


class TestSendPing:
    def test_disabled_via_settings_sends_nothing(self, db: Session) -> None:
        with (
            patch.object(settings, "telemetry_enabled", False),
            patch("app.services.telemetry_service.httpx.post") as mock_post,
        ):
            result = telemetry_service.send_ping(db, event="daily")

        assert result == "disabled"
        mock_post.assert_not_called()

    def test_daily_ping_not_due_within_24_hours(self, db: Session) -> None:
        state = telemetry_service.get_or_create_state(db)
        state.last_sent_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()

        with patch("app.services.telemetry_service.httpx.post") as mock_post:
            result = telemetry_service.send_ping(db, event="daily")

        assert result == "not_due"
        mock_post.assert_not_called()

    def test_startup_ping_debounced_within_12_hours(self, db: Session) -> None:
        state = telemetry_service.get_or_create_state(db)
        state.last_sent_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()

        with patch("app.services.telemetry_service.httpx.post") as mock_post:
            result = telemetry_service.send_ping(db, event="startup")

        assert result == "not_due"
        mock_post.assert_not_called()

    def test_startup_ping_sent_after_debounce_window(self, db: Session) -> None:
        state = telemetry_service.get_or_create_state(db)
        state.last_sent_at = datetime.now(timezone.utc) - timedelta(hours=13)
        db.flush()

        with patch("app.services.telemetry_service.httpx.post", return_value=MagicMock()) as mock_post:
            result = telemetry_service.send_ping(db, event="startup")

        assert result == "sent"
        mock_post.assert_called_once()

    def test_sent_ping_updates_last_sent_at(self, db: Session) -> None:
        with patch("app.services.telemetry_service.httpx.post", return_value=MagicMock()) as mock_post:
            result = telemetry_service.send_ping(db, event="daily")

        assert result == "sent"
        state = telemetry_service.get_or_create_state(db)
        assert state.last_sent_at is not None

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["event"] == "daily"
        assert call_kwargs["timeout"] == 5.0

    def test_delivery_error_propagates_and_leaves_state_untouched(self, db: Session) -> None:
        with (
            patch(
                "app.services.telemetry_service.httpx.post",
                side_effect=httpx.ConnectError("connection refused"),
            ),
            pytest.raises(httpx.ConnectError),
        ):
            telemetry_service.send_ping(db, event="daily")

        state = telemetry_service.get_or_create_state(db)
        assert state.last_sent_at is None
