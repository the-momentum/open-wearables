"""Tests for Oura webhook schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.oura.imports import OuraWebhookNotification


class TestOuraWebhookNotification:
    """Test webhook notification payload parsing."""

    def test_parse_valid_notification(self) -> None:
        payload = {
            "event_type": "create",
            "data_type": "daily_sleep",
            "user_id": "oura-user-123",
            "event_timestamp": "2024-01-15T08:00:00+00:00",
            "data_timestamp": "2024-01-15",
        }
        notification = OuraWebhookNotification(**payload)

        assert notification.event_type == "create"
        assert notification.data_type == "daily_sleep"
        assert notification.user_id == "oura-user-123"
        assert notification.event_timestamp == "2024-01-15T08:00:00+00:00"
        assert notification.data_timestamp == "2024-01-15"

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
        assert notification.event_timestamp is None
        assert notification.data_timestamp is None

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
