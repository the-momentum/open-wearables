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
    PersonalRecordFactory,
    SeriesTypeDefinitionFactory,
    SleepDetailsFactory,
    UserFactory,
    WorkoutDetailsFactory,
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


class TestActivitySummaryEndpoint:
    """Test suite for activity summaries endpoint."""

    def test_get_activity_summary_empty(self, client: TestClient, db: Session) -> None:
        """Test activity summary returns empty data when no data points exist."""
        user = UserFactory()
        api_key = ApiKeyFactory()

        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["has_more"] is False

    def test_get_activity_summary_with_steps(self, client: TestClient, db: Session) -> None:
        """Test activity summary aggregates step data by day."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create step data for a day (multiple data points)
        base_time = datetime(2025, 12, 26, 8, 0, 0, tzinfo=timezone.utc)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=base_time,
        )
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("500"),
            recorded_at=base_time + timedelta(hours=1),
        )
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("750"),
            recorded_at=base_time + timedelta(hours=2),
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["date"] == "2025-12-26"
        assert activity["steps"] == 2250  # Sum of all steps
        assert activity["source"]["provider"] == "apple"

    def test_get_activity_summary_with_calories(self, client: TestClient, db: Session) -> None:
        """Test activity summary aggregates calorie data."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="garmin")
        energy_type = SeriesTypeDefinitionFactory.get_or_create_energy()
        basal_type = SeriesTypeDefinitionFactory.get_or_create_basal_energy()

        base_time = datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc)

        # Active calories
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=energy_type,
            value=Decimal("250.5"),
            recorded_at=base_time,
        )
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=energy_type,
            value=Decimal("150.0"),
            recorded_at=base_time + timedelta(hours=2),
        )

        # Basal calories
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=basal_type,
            value=Decimal("1600.0"),
            recorded_at=base_time,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["active_calories_kcal"] == 400.5  # 250.5 + 150.0
        assert activity["total_calories_kcal"] == 2000.5  # 400.5 + 1600.0

    def test_get_activity_summary_with_heart_rate(self, client: TestClient, db: Session) -> None:
        """Test activity summary includes heart rate statistics."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="polar")
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        base_time = datetime(2025, 12, 26, 9, 0, 0, tzinfo=timezone.utc)

        # Create multiple HR data points
        for i, hr in enumerate([65, 120, 145, 90, 72]):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                value=Decimal(str(hr)),
                recorded_at=base_time + timedelta(minutes=i * 10),
            )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["heart_rate"] is not None
        assert activity["heart_rate"]["avg_bpm"] == 98  # avg of 65, 120, 145, 90, 72 = 98.4 -> 98
        assert activity["heart_rate"]["max_bpm"] == 145
        assert activity["heart_rate"]["min_bpm"] == 65

    def test_get_activity_summary_with_all_metrics(self, client: TestClient, db: Session) -> None:
        """Test activity summary with all available metrics."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")

        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        energy_type = SeriesTypeDefinitionFactory.get_or_create_energy()
        basal_type = SeriesTypeDefinitionFactory.get_or_create_basal_energy()
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        distance_type = SeriesTypeDefinitionFactory.get_or_create_distance_walking_running()
        flights_type = SeriesTypeDefinitionFactory.get_or_create_flights_climbed()

        base_time = datetime(2025, 12, 26, 8, 0, 0, tzinfo=timezone.utc)

        # Steps
        DataPointSeriesFactory(mapping=mapping, series_type=steps_type, value=Decimal("8500"), recorded_at=base_time)

        # Energy
        DataPointSeriesFactory(mapping=mapping, series_type=energy_type, value=Decimal("350.0"), recorded_at=base_time)
        DataPointSeriesFactory(mapping=mapping, series_type=basal_type, value=Decimal("1800.0"), recorded_at=base_time)

        # Heart rate
        DataPointSeriesFactory(mapping=mapping, series_type=hr_type, value=Decimal("75"), recorded_at=base_time)
        DataPointSeriesFactory(
            mapping=mapping, series_type=hr_type, value=Decimal("130"), recorded_at=base_time + timedelta(hours=1)
        )

        # Distance
        DataPointSeriesFactory(
            mapping=mapping, series_type=distance_type, value=Decimal("6200.5"), recorded_at=base_time
        )

        # Flights climbed
        DataPointSeriesFactory(mapping=mapping, series_type=flights_type, value=Decimal("12"), recorded_at=base_time)

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["date"] == "2025-12-26"
        assert activity["source"]["provider"] == "apple"
        assert activity["steps"] == 8500
        assert activity["distance_meters"] == 6200.5
        assert activity["floors_climbed"] == 12
        assert activity["active_calories_kcal"] == 350.0
        assert activity["total_calories_kcal"] == 2150.0  # 350 + 1800
        assert activity["heart_rate"]["avg_bpm"] == 102  # avg(75, 130) = 102.5 -> 102
        assert activity["heart_rate"]["max_bpm"] == 130
        assert activity["heart_rate"]["min_bpm"] == 75

        # Active/sedentary based on step threshold (30 steps/min)
        # 8500 steps in one minute bucket -> 1 active minute
        assert activity["active_minutes"] == 1
        assert activity["sedentary_minutes"] == 0

        # Intensity based on HR zones (using default max HR 190)
        # HR values: 75 (below light), 130 (moderate: 122-144)
        # 75 bpm is below 50% of 190 (95), so not counted
        # 130 bpm is in moderate zone (64-76% of 190 = 122-144)
        assert activity["intensity_minutes"] is not None
        assert activity["intensity_minutes"]["moderate"] == 1

    def test_get_activity_summary_multiple_days(self, client: TestClient, db: Session) -> None:
        """Test activity summary returns data grouped by day."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="suunto")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Day 1 - Dec 26
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("5000"),
            recorded_at=datetime(2025, 12, 26, 12, 0, 0, tzinfo=timezone.utc),
        )

        # Day 2 - Dec 27
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("7500"),
            recorded_at=datetime(2025, 12, 27, 14, 0, 0, tzinfo=timezone.utc),
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-28T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

        # Ordered by date ascending
        assert data["data"][0]["date"] == "2025-12-26"
        assert data["data"][0]["steps"] == 5000
        assert data["data"][1]["date"] == "2025-12-27"
        assert data["data"][1]["steps"] == 7500

    def test_get_activity_summary_with_elevation(self, client: TestClient, db: Session) -> None:
        """Test activity summary includes elevation from workouts."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="garmin")

        # Create a workout with elevation data
        workout_start = datetime(2025, 12, 26, 8, 0, 0, tzinfo=timezone.utc)
        workout_end = datetime(2025, 12, 26, 9, 30, 0, tzinfo=timezone.utc)

        event_record = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
            start_datetime=workout_start,
            end_datetime=workout_end,
            duration_seconds=5400,
        )

        WorkoutDetailsFactory(
            event_record=event_record,
            total_elevation_gain=Decimal("150.5"),  # 150.5 meters
            distance=Decimal("10000.0"),  # 10km
        )

        # Also add some step data for the same day
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("12000"),
            recorded_at=workout_end,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["date"] == "2025-12-26"
        assert activity["steps"] == 12000
        assert activity["elevation_meters"] == 150.5
        # floors_climbed calculated from elevation: 150.5 / 3 = 50
        assert activity["floors_climbed"] == 50
        # Distance is from time-series only (not workout), so None here
        assert activity["distance_meters"] is None

    def test_get_activity_summary_floors_from_flights_preferred(self, client: TestClient, db: Session) -> None:
        """Test that flights_climbed is preferred over elevation for floors calculation."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")

        # Create workout with elevation
        workout_start = datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc)
        workout_end = datetime(2025, 12, 26, 11, 0, 0, tzinfo=timezone.utc)

        event_record = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="hiking",
            start_datetime=workout_start,
            end_datetime=workout_end,
            duration_seconds=3600,
        )

        WorkoutDetailsFactory(
            event_record=event_record,
            total_elevation_gain=Decimal("90.0"),  # 90m = 30 floors if calculated
        )

        # Also add flights_climbed time-series (should be preferred)
        flights_type = SeriesTypeDefinitionFactory.get_or_create_flights_climbed()
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=flights_type,
            value=Decimal("25"),  # 25 flights from barometer
            recorded_at=workout_end,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        # floors_climbed should be 25 from flights_climbed (not 30 from elevation/3)
        assert activity["floors_climbed"] == 25
        # elevation_meters should still show the raw value
        assert activity["elevation_meters"] == 90.0

    def test_get_activity_summary_with_active_sedentary_minutes(self, client: TestClient, db: Session) -> None:
        """Test activity summary calculates active/sedentary minutes from step data."""
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create step data at minute intervals
        # Active minutes: 3 minutes with >= 30 steps
        # Sedentary minutes: 2 minutes with < 30 steps
        base_time = datetime(2025, 12, 26, 9, 0, 0, tzinfo=timezone.utc)

        # Minute 1: 50 steps (active)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("50"),
            recorded_at=base_time,
        )
        # Minute 2: 10 steps (sedentary)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("10"),
            recorded_at=base_time + timedelta(minutes=1),
        )
        # Minute 3: 45 steps (active)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("45"),
            recorded_at=base_time + timedelta(minutes=2),
        )
        # Minute 4: 5 steps (sedentary)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("5"),
            recorded_at=base_time + timedelta(minutes=3),
        )
        # Minute 5: 60 steps (active)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("60"),
            recorded_at=base_time + timedelta(minutes=4),
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        # 3 minutes with >= 30 steps (50, 45, 60)
        assert activity["active_minutes"] == 3
        # 2 minutes with < 30 steps (10, 5)
        assert activity["sedentary_minutes"] == 2
        # Total steps: 50 + 10 + 45 + 5 + 60 = 170
        assert activity["steps"] == 170

    def test_get_activity_summary_with_intensity_minutes(self, client: TestClient, db: Session) -> None:
        """Test activity summary calculates intensity minutes from HR data.

        Uses a 30-year-old user: max HR = 220 - 30 = 190 bpm
        - Light: 50-63% of 190 = 95-120 bpm
        - Moderate: 64-76% of 190 = 122-144 bpm
        - Vigorous: 77-93% of 190 = 146-177 bpm
        """
        from datetime import date

        user = UserFactory()
        # Create personal record with birth_date for a 30-year-old
        PersonalRecordFactory(user=user, birth_date=date(1995, 1, 1))

        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        base_time = datetime(2025, 12, 26, 9, 0, 0, tzinfo=timezone.utc)

        # Create HR data at different zones (user age 30, max HR = 190)
        # Minute 1: 100 bpm (light: 50-63% of 190 = 95-120)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("100"),
            recorded_at=base_time,
        )
        # Minute 2: 110 bpm (light)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("110"),
            recorded_at=base_time + timedelta(minutes=1),
        )
        # Minute 3: 130 bpm (moderate: 64-76% of 190 = 122-144)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("130"),
            recorded_at=base_time + timedelta(minutes=2),
        )
        # Minute 4: 140 bpm (moderate)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("140"),
            recorded_at=base_time + timedelta(minutes=3),
        )
        # Minute 5: 160 bpm (vigorous: 77-93% of 190 = 146-177)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("160"),
            recorded_at=base_time + timedelta(minutes=4),
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["intensity_minutes"] is not None
        # 2 light minutes (100, 110)
        assert activity["intensity_minutes"]["light"] == 2
        # 2 moderate minutes (130, 140)
        assert activity["intensity_minutes"]["moderate"] == 2
        # 1 vigorous minute (160)
        assert activity["intensity_minutes"]["vigorous"] == 1

    def test_get_activity_summary_intensity_without_birth_date(self, client: TestClient, db: Session) -> None:
        """Test activity summary uses default max HR when birth_date is not available.

        Default max HR = 190 (assumes ~30 years old)
        """
        user = UserFactory()
        # No personal record, so no birth_date

        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple")
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        base_time = datetime(2025, 12, 26, 9, 0, 0, tzinfo=timezone.utc)

        # Create HR data that would be in moderate zone for max HR = 190
        # Moderate: 64-76% of 190 = 122-144 bpm
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            value=Decimal("135"),
            recorded_at=base_time,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.id),
            params={"start_date": "2025-12-25T00:00:00Z", "end_date": "2025-12-27T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

        activity = data["data"][0]
        assert activity["intensity_minutes"] is not None
        assert activity["intensity_minutes"]["moderate"] == 1
