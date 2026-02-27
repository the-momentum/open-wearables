"""Tests for Oura webhook schemas and service."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.oura.imports import OuraWebhookNotification
from app.services.providers.oura.webhook_service import OuraWebhookService


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


class TestOuraWebhookServiceTimestampParsing:
    """Test the service's timestamp parsing logic."""

    def test_parse_data_timestamp_with_date(self) -> None:
        notification = OuraWebhookNotification(
            event_type="create",
            data_type="daily_sleep",
            user_id="test",
            data_timestamp="2024-01-15",
        )
        start, end = OuraWebhookService._parse_data_timestamp(notification)

        assert start.year == 2024
        assert start.month == 1
        assert start.day == 15
        assert start.hour == 0
        assert start.minute == 0
        assert end.day == 16

    def test_parse_data_timestamp_with_iso_datetime(self) -> None:
        notification = OuraWebhookNotification(
            event_type="create",
            data_type="workout",
            user_id="test",
            data_timestamp="2024-03-20T14:30:00+00:00",
        )
        start, end = OuraWebhookService._parse_data_timestamp(notification)

        assert start.day == 20
        assert start.month == 3
        assert end.day == 21

    def test_parse_data_timestamp_missing_falls_back_to_utc_now(self) -> None:
        notification = OuraWebhookNotification(
            event_type="create",
            data_type="daily_activity",
            user_id="test",
        )
        start, end = OuraWebhookService._parse_data_timestamp(notification)

        now = datetime.now(timezone.utc)
        assert start.day == now.day
        assert start.hour == 0

    def test_parse_data_timestamp_invalid_falls_back_to_utc_now(self) -> None:
        notification = OuraWebhookNotification(
            event_type="create",
            data_type="daily_readiness",
            user_id="test",
            data_timestamp="not-a-date",
        )
        start, end = OuraWebhookService._parse_data_timestamp(notification)

        now = datetime.now(timezone.utc)
        assert start.day == now.day
