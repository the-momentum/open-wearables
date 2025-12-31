"""Tests for summaries endpoints."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, EventRecordFactory, ExternalDeviceMappingFactory, UserFactory
from tests.utils import api_key_headers


class TestSleepSummaryEndpoint:
    """Test suite for sleep summaries endpoint."""

    def test_get_sleep_summary_basic(self, client: TestClient, db: Session) -> None:
        """Test basic sleep summary returns start_time, end_time, and duration."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        sleep_end = datetime(2025, 12, 26, 5, 0, 0, tzinfo=timezone.utc)
        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=sleep_start,
            end_datetime=sleep_end,
            duration_seconds=sleep_end.timestamp() - sleep_start.timestamp(),
        )
        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["date"] == "2025-12-25"
        assert data["data"][0]["start_time"] == "2025-12-25T22:00:00Z"
        assert data["data"][0]["end_time"] == "2025-12-26T05:00:00Z"
        assert data["data"][0]["duration_seconds"] == 25200
