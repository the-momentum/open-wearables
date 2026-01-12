"""Tests for summaries endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    EventRecordFactory,
    ExternalDeviceMappingFactory,
    SeriesTypeDefinitionFactory,
    SleepDetailsFactory,
    UserFactory,
)
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
            duration_seconds=int(sleep_end.timestamp() - sleep_start.timestamp()),
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
        assert data["data"][0]["date"] == "2025-12-26"
        assert data["data"][0]["start_time"] == "2025-12-25T22:00:00Z"
        assert data["data"][0]["end_time"] == "2025-12-26T05:00:00Z"
        assert data["data"][0]["duration_minutes"] == 420  # 7 hours

    def test_get_sleep_summary_with_details(self, client: TestClient, db: Session) -> None:
        """Test sleep summary returns sleep stage details and efficiency."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        sleep_end = datetime(2025, 12, 26, 6, 0, 0, tzinfo=timezone.utc)

        # Create event record with sleep details
        event_record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=sleep_start,
            end_datetime=sleep_end,
            duration_seconds=28800,  # 8 hours
        )

        # Create sleep details with specific values
        SleepDetailsFactory(
            event_record=event_record,
            sleep_total_duration_minutes=420,  # 7 hours actual sleep
            sleep_time_in_bed_minutes=480,  # 8 hours in bed
            sleep_deep_minutes=90,  # 1.5 hours deep
            sleep_light_minutes=210,  # 3.5 hours light
            sleep_rem_minutes=90,  # 1.5 hours REM
            sleep_awake_minutes=30,  # 30 min awake
            sleep_efficiency_score=Decimal("87.5"),
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

        sleep_data = data["data"][0]
        assert sleep_data["date"] == "2025-12-26"
        assert sleep_data["duration_minutes"] == 480  # 8 hours

        # Verify sleep details are populated
        assert sleep_data["time_in_bed_minutes"] == 480
        assert sleep_data["efficiency_percent"] == 87.5

        # Verify sleep stages (values in minutes)
        assert sleep_data["stages"] is not None
        assert sleep_data["stages"]["deep_minutes"] == 90
        assert sleep_data["stages"]["light_minutes"] == 210
        assert sleep_data["stages"]["rem_minutes"] == 90
        assert sleep_data["stages"]["awake_minutes"] == 30

    def test_get_sleep_summary_with_physiological_metrics(self, client: TestClient, db: Session) -> None:
        """Test sleep summary returns physiological metrics from time-series data."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        sleep_end = datetime(2025, 12, 26, 6, 0, 0, tzinfo=timezone.utc)

        # Create event record with sleep details
        event_record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=sleep_start,
            end_datetime=sleep_end,
            duration_seconds=28800,
        )

        SleepDetailsFactory(
            event_record=event_record,
            sleep_total_duration_minutes=420,
            sleep_time_in_bed_minutes=480,
            sleep_deep_minutes=90,
            sleep_light_minutes=210,
            sleep_rem_minutes=90,
            sleep_awake_minutes=30,
            sleep_efficiency_score=Decimal("85.0"),
        )

        # Create heart rate data points during sleep (ID 1 = heart_rate)
        heart_rate_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for i in range(8):  # One reading per hour
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=heart_rate_type,
                recorded_at=sleep_start + timedelta(hours=i),
                value=Decimal("55") + Decimal(str(i)),  # 55-62 bpm range
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

        sleep_data = data["data"][0]

        # Verify basic fields
        assert sleep_data["duration_minutes"] == 480  # 8 hours
        assert sleep_data["efficiency_percent"] == 85.0
        assert sleep_data["stages"] is not None

        # Verify heart rate average is calculated
        # Average of 55, 56, 57, 58, 59, 60, 61, 62 = 58.5, rounded to 58 or 59
        assert sleep_data["avg_heart_rate_bpm"] is not None
        assert 58 <= sleep_data["avg_heart_rate_bpm"] <= 59

    def test_get_sleep_summary_no_physiological_data(self, client: TestClient, db: Session) -> None:
        """Test sleep summary handles missing physiological data gracefully."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        sleep_end = datetime(2025, 12, 26, 6, 0, 0, tzinfo=timezone.utc)

        # Create event record without any time-series data
        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=sleep_start,
            end_datetime=sleep_end,
            duration_seconds=28800,
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

        sleep_data = data["data"][0]

        # Physiological metrics should be null when no data exists
        assert sleep_data["avg_heart_rate_bpm"] is None
        assert sleep_data["avg_hrv_rmssd_ms"] is None
        assert sleep_data["avg_respiratory_rate"] is None
        assert sleep_data["avg_spo2_percent"] is None

    def test_get_sleep_summary_with_naps(self, client: TestClient, db: Session) -> None:
        """Test sleep summary tracks naps separately from main sleep."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)

        # Main nighttime sleep: 10pm - 6am (8 hours)
        main_sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        main_sleep_end = datetime(2025, 12, 26, 6, 0, 0, tzinfo=timezone.utc)
        main_sleep_record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=main_sleep_start,
            end_datetime=main_sleep_end,
            duration_seconds=28800,  # 8 hours
        )
        SleepDetailsFactory(
            event_record=main_sleep_record,
            sleep_time_in_bed_minutes=480,
            sleep_deep_minutes=90,
            sleep_light_minutes=210,
            sleep_rem_minutes=90,
            sleep_awake_minutes=30,
            sleep_efficiency_score=Decimal("85.0"),
            is_nap=False,
        )

        # Afternoon nap: 2pm - 2:30pm (30 minutes)
        nap_start = datetime(2025, 12, 26, 14, 0, 0, tzinfo=timezone.utc)
        nap_end = datetime(2025, 12, 26, 14, 30, 0, tzinfo=timezone.utc)
        nap_record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=nap_start,
            end_datetime=nap_end,
            duration_seconds=1800,  # 30 minutes
        )
        SleepDetailsFactory(
            event_record=nap_record,
            sleep_time_in_bed_minutes=30,
            sleep_deep_minutes=10,
            sleep_light_minutes=20,
            sleep_rem_minutes=0,
            sleep_awake_minutes=0,
            sleep_efficiency_score=Decimal("95.0"),
            is_nap=True,
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

        sleep_data = data["data"][0]
        assert sleep_data["date"] == "2025-12-26"

        # Main sleep metrics should EXCLUDE nap
        assert sleep_data["start_time"] == "2025-12-25T22:00:00Z"  # Main sleep start, not nap
        assert sleep_data["end_time"] == "2025-12-26T06:00:00Z"  # Main sleep end, not nap
        assert sleep_data["duration_minutes"] == 480  # Only main sleep (8 hours)
        assert sleep_data["time_in_bed_minutes"] == 480  # Only main sleep time in bed
        assert sleep_data["efficiency_percent"] == 85.0  # Only main sleep efficiency

        # Sleep stages should be main sleep only
        assert sleep_data["stages"]["deep_minutes"] == 90
        assert sleep_data["stages"]["light_minutes"] == 210

        # Nap tracking
        assert sleep_data["nap_count"] == 1
        assert sleep_data["nap_duration_minutes"] == 30

    def test_get_sleep_summary_no_naps(self, client: TestClient, db: Session) -> None:
        """Test sleep summary returns null for nap fields when no naps exist."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        sleep_start = datetime(2025, 12, 25, 22, 0, 0, tzinfo=timezone.utc)
        sleep_end = datetime(2025, 12, 26, 6, 0, 0, tzinfo=timezone.utc)

        event_record = EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=sleep_start,
            end_datetime=sleep_end,
            duration_seconds=28800,
        )
        SleepDetailsFactory(
            event_record=event_record,
            sleep_time_in_bed_minutes=480,
            sleep_efficiency_score=Decimal("90.0"),
            is_nap=False,
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

        sleep_data = data["data"][0]

        # Nap fields should be 0 when we have sleep data but no naps
        assert sleep_data["nap_count"] == 0
        assert sleep_data["nap_duration_minutes"] == 0

        # Main sleep should still be tracked
        assert sleep_data["duration_minutes"] == 480  # 8 hours
        assert sleep_data["efficiency_percent"] == 90.0
