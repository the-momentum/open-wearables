"""Tests for Oura webhook schemas and service."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemas.providers.oura import OuraWebhookNotification
from app.services.providers.factory import ProviderFactory
from tests.factories import UserConnectionFactory

OURA_USER_ID = "oura-user-1825"


class TestOuraWebhookNotification:
    """Test webhook notification payload parsing."""

    def test_parse_valid_notification(self) -> None:
        payload = {
            "event_type": "create",
            "data_type": "daily_sleep",
            "user_id": "oura-user-123",
            "object_id": "abc-123",
            "event_time": "2024-01-15T08:00:00+00:00",
        }
        notification = OuraWebhookNotification(**payload)

        assert notification.event_type == "create"
        assert notification.data_type == "daily_sleep"
        assert notification.user_id == "oura-user-123"
        assert notification.object_id == "abc-123"
        assert notification.event_time == "2024-01-15T08:00:00+00:00"

    def test_parse_minimal_notification(self) -> None:
        payload = {
            "event_type": "update",
            "data_type": "workout",
            "user_id": "oura-user-456",
        }
        notification = OuraWebhookNotification(**payload)

        assert notification.event_type == "update"
        assert notification.data_type == "workout"
        assert notification.user_id == "oura-user-456"
        assert notification.object_id is None
        assert notification.event_time is None

    def test_parse_delete_event(self) -> None:
        payload = {
            "event_type": "delete",
            "data_type": "daily_activity",
            "user_id": "oura-user-789",
        }
        notification = OuraWebhookNotification(**payload)
        assert notification.event_type == "delete"

    def test_missing_required_field_raises_error(self) -> None:
        payload = {
            "event_type": "create",
            "data_type": "daily_sleep",
            # missing user_id
        }
        with pytest.raises(ValidationError):
            OuraWebhookNotification(**payload)

    def test_all_data_types(self) -> None:
        data_types = [
            "daily_activity",
            "daily_readiness",
            "daily_sleep",
            "daily_spo2",
            "workout",
            "tag",
        ]
        for dt in data_types:
            notification = OuraWebhookNotification(
                event_type="create",
                data_type=dt,
                user_id="test-user",
            )
            assert notification.data_type == dt


class TestOuraWebhookLastSyncedAt:
    """last_synced_at moves only after a completed fetch."""

    @pytest.fixture
    def handler(self) -> Any:
        return ProviderFactory().get_provider("oura").webhooks

    @staticmethod
    def _connection() -> Any:
        return UserConnectionFactory(
            provider="oura",
            provider_user_id=OURA_USER_ID,
            last_synced_at=datetime.now(timezone.utc) - timedelta(days=3),
        )

    @staticmethod
    def _payload(**overrides: Any) -> dict[str, Any]:
        return {"event_type": "create", "data_type": "daily_spo2", "user_id": OURA_USER_ID, **overrides}

    def test_missing_object_id_is_ignored_without_fetch(self, db: Session, handler: Any) -> None:
        connection = self._connection()
        before = connection.last_synced_at

        with patch.object(handler.data_247, "_make_api_request") as api:
            result = handler.process_payload(db, self._payload(), "trace-1")
        db.refresh(connection)

        api.assert_not_called()
        assert result["status"] == "ignored"
        assert result["reason"] == "missing_object_id"
        assert connection.last_synced_at == before

    def test_unhandled_data_type_keeps_last_synced_at(self, db: Session, handler: Any) -> None:
        connection = self._connection()
        before = connection.last_synced_at

        with (
            patch.object(handler.data_247, "_make_api_request", return_value={"id": "tag-1"}),
            patch("app.services.providers.oura.webhook_handler.store_raw_payload"),
        ):
            result = handler.process_payload(db, self._payload(data_type="tag", object_id="tag-1"), "trace-2")
        db.refresh(connection)

        assert result["status"] == "ignored"
        assert result["reason"] == "unhandled_data_type: tag"
        assert connection.last_synced_at == before

    def test_completed_fetch_updates_last_synced_at(self, db: Session, handler: Any) -> None:
        connection = self._connection()
        before = connection.last_synced_at

        with patch.object(handler.data_247, "_make_api_request", return_value={}) as api:
            result = handler.process_payload(db, self._payload(object_id="spo2-1"), "trace-3")
        db.refresh(connection)

        api.assert_called_once()
        assert result["status"] == "processed"
        assert result["records_saved"] == 0
        assert connection.last_synced_at > before
