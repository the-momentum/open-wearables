"""Tests for Garmin 247 data implementation."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.oauth import GarminOAuth
from tests.factories import UserConnectionFactory, UserFactory


class TestGarmin247Data:
    """Tests for Garmin247Data class."""

    @pytest.fixture
    def garmin_247(self, db: Session) -> Garmin247Data:
        """Create Garmin247Data instance for testing."""
        connection_repo = UserConnectionRepository()
        oauth = GarminOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )
        return Garmin247Data(
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
            oauth=oauth,
        )

    @pytest.fixture
    def sample_sleep(self) -> dict[str, Any]:
        """Sample Garmin sleep data."""
        return {
            "summaryId": "sleep_123",
            "calendarDate": "2024-01-15",
            "startTimeInSeconds": 1705273200,  # 2024-01-14 22:00:00 UTC
            "durationInSeconds": 28800,  # 8 hours
            "deepSleepDurationInSeconds": 7200,  # 2 hours
            "lightSleepDurationInSeconds": 14400,  # 4 hours
            "remSleepInSeconds": 5400,  # 1.5 hours
            "awakeDurationInSeconds": 1800,  # 30 minutes
            "averageHeartRate": 58,
            "lowestHeartRate": 48,
            "respirationAvg": 14.5,
            "avgOxygenSaturation": 96.5,
            "validation": "DEVICE",
        }

    @pytest.fixture
    def sample_daily(self) -> dict[str, Any]:
        """Sample Garmin daily summary data."""
        return {
            "summaryId": "daily_123",
            "calendarDate": "2024-01-15",
            "startTimeInSeconds": 1705276800,  # 2024-01-15 00:00:00 UTC
            "durationInSeconds": 86400,  # 24 hours
            "steps": 12500,
            "distanceInMeters": 9500.5,
            "activeKilocalories": 650,
            "bmrKilocalories": 1800,
            "floorsClimbed": 12,
            "restingHeartRateInBeatsPerMinute": 55,
            "averageHeartRateInBeatsPerMinute": 72,
            "averageStressLevel": 35,
            "timeOffsetHeartRateSamples": {
                "0": 60,
                "900": 65,
                "1800": 70,
            },
        }

    @pytest.fixture
    def sample_epoch(self) -> dict[str, Any]:
        """Sample Garmin epoch data (15-minute interval)."""
        return {
            "summaryId": "epoch_123",
            "startTimeInSeconds": 1705309200,  # 2024-01-15 09:00:00 UTC
            "durationInSeconds": 900,  # 15 minutes
            "steps": 250,
            "distanceInMeters": 200.5,
            "activeKilocalories": 15,
            "meanHeartRateInBeatsPerMinute": 85,
            "maxHeartRateInBeatsPerMinute": 95,
            "intensity": "ACTIVE",
        }

    @pytest.fixture
    def sample_body_comp(self) -> dict[str, Any]:
        """Sample Garmin body composition data."""
        return {
            "summaryId": "bodycomp_123",
            "measurementTimeInSeconds": 1705320000,  # 2024-01-15 12:00:00 UTC
            "weightInGrams": 75000,  # 75 kg
            "bodyFatInPercent": 18.5,
            "bodyMassIndex": 23.5,
            "muscleMassInGrams": 35000,
        }

    # -------------------------------------------------------------------------
    # Helper Method Tests
    # -------------------------------------------------------------------------

    def test_epoch_seconds_conversion(self, garmin_247: Garmin247Data) -> None:
        """Test datetime to Unix timestamp conversion."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = garmin_247._epoch_seconds(dt)
        assert result == 1705320000

    def test_from_epoch_seconds_conversion(self, garmin_247: Garmin247Data) -> None:
        """Test Unix timestamp to datetime conversion."""
        result = garmin_247._from_epoch_seconds(1705320000)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.tzinfo == timezone.utc

    def test_fetch_in_chunks_single_chunk(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test chunked fetching for date range under 24 hours."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)  # 12 hours

        with patch.object(garmin_247, "_make_api_request", return_value=[{"id": "1"}]) as mock_request:
            result = garmin_247._fetch_in_chunks(db, user.id, "/test", start, end)

            # Should make only 1 request for 12-hour range
            assert mock_request.call_count == 1
            assert len(result) == 1

    def test_fetch_in_chunks_multiple_chunks(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test chunked fetching for date range over 24 hours."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)  # 2 days

        with patch.object(garmin_247, "_make_api_request", return_value=[{"id": "1"}]) as mock_request:
            result = garmin_247._fetch_in_chunks(db, user.id, "/test", start, end)

            # Should make 2 requests for 48-hour range (24h chunks)
            assert mock_request.call_count == 2
            assert len(result) == 2

    def test_fetch_in_chunks_handles_errors(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test chunked fetching continues on error."""
        user = UserFactory()

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)

        # First call raises error, second succeeds
        with patch.object(
            garmin_247,
            "_make_api_request",
            side_effect=[Exception("API Error"), [{"id": "2"}]],
        ) as mock_request:
            result = garmin_247._fetch_in_chunks(db, user.id, "/test", start, end)

            # Should still return data from successful request
            assert mock_request.call_count == 2
            assert len(result) == 1

    # -------------------------------------------------------------------------
    # Sleep Data Tests
    # -------------------------------------------------------------------------

    def test_normalize_sleep(self, garmin_247: Garmin247Data, sample_sleep: dict[str, Any]) -> None:
        """Test normalizing sleep data."""
        user_id = uuid4()
        normalized = garmin_247.normalize_sleep(sample_sleep, user_id)

        assert normalized["user_id"] == user_id
        assert normalized["provider"] == "garmin"
        assert normalized["duration_seconds"] == 28800
        assert normalized["garmin_summary_id"] == "sleep_123"

        # Sleep stages
        stages = normalized["stages"]
        assert stages["deep_seconds"] == 7200
        assert stages["light_seconds"] == 14400
        assert stages["rem_seconds"] == 5400
        assert stages["awake_seconds"] == 1800

        # Heart rate and respiration
        assert normalized["avg_heart_rate_bpm"] == 58
        assert normalized["min_heart_rate_bpm"] == 48
        assert normalized["avg_respiration"] == 14.5

    def test_normalize_sleep_missing_stages(self, garmin_247: Garmin247Data) -> None:
        """Test normalizing sleep with missing stage data."""
        user_id = uuid4()
        sleep_data = {
            "summaryId": "sleep_123",
            "startTimeInSeconds": 1705273200,
            "durationInSeconds": 28800,
        }

        normalized = garmin_247.normalize_sleep(sleep_data, user_id)

        # Should handle missing stage data gracefully
        stages = normalized["stages"]
        assert stages["deep_seconds"] == 0
        assert stages["light_seconds"] == 0
        assert stages["rem_seconds"] == 0
        assert stages["awake_seconds"] == 0

    # -------------------------------------------------------------------------
    # Dailies Data Tests
    # -------------------------------------------------------------------------

    def test_normalize_dailies(self, garmin_247: Garmin247Data, sample_daily: dict[str, Any]) -> None:
        """Test normalizing daily summary data."""
        user_id = uuid4()
        normalized = garmin_247.normalize_dailies(sample_daily, user_id)

        assert normalized["user_id"] == user_id
        assert normalized["calendar_date"] == "2024-01-15"
        assert normalized["steps"] == 12500
        assert normalized["distance_meters"] == 9500.5
        assert normalized["active_calories"] == 650
        assert normalized["resting_heart_rate"] == 55
        assert normalized["floors_climbed"] == 12
        assert normalized["avg_stress"] == 35

        # Heart rate samples
        assert "heart_rate_samples" in normalized
        assert normalized["heart_rate_samples"]["0"] == 60

    def test_normalize_dailies_missing_values(self, garmin_247: Garmin247Data) -> None:
        """Test normalizing daily data with missing values."""
        user_id = uuid4()
        daily_data = {
            "summaryId": "daily_123",
            "calendarDate": "2024-01-15",
            "startTimeInSeconds": 1705276800,
            "durationInSeconds": 86400,
        }

        normalized = garmin_247.normalize_dailies(daily_data, user_id)

        assert normalized["steps"] is None
        assert normalized["active_calories"] is None
        assert normalized["resting_heart_rate"] is None

    # -------------------------------------------------------------------------
    # Epochs Data Tests
    # -------------------------------------------------------------------------

    def test_normalize_epochs(self, garmin_247: Garmin247Data, sample_epoch: dict[str, Any]) -> None:
        """Test normalizing epoch data."""
        user_id = uuid4()
        epochs = [sample_epoch]

        normalized = garmin_247.normalize_epochs(epochs, user_id)

        assert "heart_rate" in normalized
        assert "steps" in normalized
        assert "energy" in normalized

        assert len(normalized["heart_rate"]) == 1
        assert normalized["heart_rate"][0]["value"] == 85

        assert len(normalized["steps"]) == 1
        assert normalized["steps"][0]["value"] == 250

    def test_normalize_epochs_multiple(self, garmin_247: Garmin247Data) -> None:
        """Test normalizing multiple epochs."""
        user_id = uuid4()
        epochs = [
            {
                "summaryId": "epoch_1",
                "startTimeInSeconds": 1705309200,
                "durationInSeconds": 900,
                "steps": 100,
                "meanHeartRateInBeatsPerMinute": 70,
            },
            {
                "summaryId": "epoch_2",
                "startTimeInSeconds": 1705310100,  # 15 minutes later
                "durationInSeconds": 900,
                "steps": 150,
                "meanHeartRateInBeatsPerMinute": 75,
            },
        ]

        normalized = garmin_247.normalize_epochs(epochs, user_id)

        assert len(normalized["heart_rate"]) == 2
        assert len(normalized["steps"]) == 2

    # -------------------------------------------------------------------------
    # Body Composition Tests
    # -------------------------------------------------------------------------

    @patch("app.repositories.data_point_series_repository.DataPointSeriesRepository.bulk_create")
    def test_save_body_composition(
        self,
        mock_bulk_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
        sample_body_comp: dict[str, Any],
    ) -> None:
        """Test saving body composition data."""
        user = UserFactory()

        count = garmin_247.save_body_composition(db, user.id, sample_body_comp)

        # Should create 3 data points: weight, body_fat, BMI
        mock_bulk_create.assert_called_once()
        assert len(mock_bulk_create.call_args[0][1]) == 3
        assert count == 3

    def test_save_body_composition_missing_timestamp(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test saving body composition with missing timestamp."""
        user_id = uuid4()
        body_comp = {"summaryId": "bc_123", "weightInGrams": 75000}

        count = garmin_247.save_body_composition(db, user_id, body_comp)

        # Should return 0 if no timestamp
        assert count == 0

    # -------------------------------------------------------------------------
    # Abstract Method Implementation Tests
    # -------------------------------------------------------------------------

    def test_get_recovery_data_returns_empty(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test that get_recovery_data returns empty list (Garmin doesn't have recovery endpoint)."""
        user_id = uuid4()
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = datetime(2024, 1, 16, tzinfo=timezone.utc)

        result = garmin_247.get_recovery_data(db, user_id, start, end)

        assert result == []

    def test_normalize_recovery_returns_empty(self, garmin_247: Garmin247Data) -> None:
        """Test that normalize_recovery returns empty dict."""
        result = garmin_247.normalize_recovery({}, uuid4())
        assert result == {}

    # -------------------------------------------------------------------------
    # Integration Tests (with mocks)
    # -------------------------------------------------------------------------

    def test_load_and_save_all_is_noop(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all is a no-op (data arrives via webhooks)."""
        user = UserFactory()

        results = garmin_247.load_and_save_all(db, user.id)

        assert results["sync_complete"] is True
        assert results["total_saved"] == 0
        assert "webhooks" in results["message"].lower()

    def test_load_and_save_all_with_dates_is_noop(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all with custom dates is still a no-op."""
        user = UserFactory()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 7, tzinfo=timezone.utc)

        results = garmin_247.load_and_save_all(db, user.id, start_time=start, end_time=end)

        assert results["sync_complete"] is True
        assert results["total_saved"] == 0

    def test_load_and_save_all_string_dates_is_noop(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all with ISO string dates is still a no-op."""
        user = UserFactory()

        results = garmin_247.load_and_save_all(
            db,
            user.id,
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-07T00:00:00Z",
        )

        assert results["sync_complete"] is True

    # -------------------------------------------------------------------------
    # HRV Data Tests
    # -------------------------------------------------------------------------

    def test_save_hrv_data(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test saving HRV data."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        hrv_data = {
            "userId": "garmin_user_123",
            "summaryId": "hrv-123",
            "calendarDate": "2026-01-14",
            "lastNightAvg": 84,
            "lastNight5MinHigh": 124,
            "startTimeOffsetInSeconds": 3600,
            "durationInSeconds": 36565,
            "startTimeInSeconds": 1768340715,
            "hrvValues": {
                "265": 70,
                "565": 73,
                "865": 68,
            },
        }

        count = garmin_247.save_hrv_data(db, user.id, hrv_data)

        # Should save 1 lastNightAvg + 3 hrvValues = 4 records
        assert count == 4

    def test_save_hrv_data_missing_start_time(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test saving HRV data with missing start time."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        hrv_data = {
            "userId": "garmin_user_123",
            "lastNightAvg": 84,
            # Missing startTimeInSeconds
        }

        count = garmin_247.save_hrv_data(db, user.id, hrv_data)

        assert count == 0

    def test_save_hrv_data_only_avg(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test saving HRV data with only lastNightAvg."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        hrv_data = {
            "userId": "garmin_user_123",
            "summaryId": "hrv-123",
            "calendarDate": "2026-01-14",
            "lastNightAvg": 84,
            "startTimeInSeconds": 1768340715,
            # No hrvValues
        }

        count = garmin_247.save_hrv_data(db, user.id, hrv_data)

        # Should save just the lastNightAvg
        assert count == 1

    # -------------------------------------------------------------------------
    # Build Method Tests (no DB interaction)
    # -------------------------------------------------------------------------

    def test_build_dailies_samples(self, garmin_247: Garmin247Data, sample_daily: dict[str, Any]) -> None:
        """Test _build_dailies_samples returns samples without DB call."""
        user_id = uuid4()
        normalized = garmin_247.normalize_dailies(sample_daily, user_id)
        samples = garmin_247._build_dailies_samples(user_id, normalized)

        # 5 metrics (steps, calories, resting_hr, floors, distance) + 3 HR samples
        assert len(samples) == 8
        assert len({s.series_type for s in samples}) > 1

    def test_build_dailies_samples_empty_on_missing_date(self, garmin_247: Garmin247Data) -> None:
        """Test _build_dailies_samples returns empty for missing date/timestamp."""
        user_id = uuid4()
        normalized = {"user_id": user_id}
        samples = garmin_247._build_dailies_samples(user_id, normalized)
        assert samples == []

    def test_build_epochs_samples(self, garmin_247: Garmin247Data, sample_epoch: dict[str, Any]) -> None:
        """Test _build_epochs_samples returns samples without DB call."""
        user_id = uuid4()
        normalized = garmin_247.normalize_epochs([sample_epoch], user_id)
        samples = garmin_247._build_epochs_samples(user_id, normalized)

        # 1 heart_rate + 1 steps + 1 energy = 3
        assert len(samples) == 3

    def test_build_body_comp_samples(self, garmin_247: Garmin247Data, sample_body_comp: dict[str, Any]) -> None:
        """Test _build_body_comp_samples returns samples without DB call."""
        user_id = uuid4()
        samples = garmin_247._build_body_comp_samples(user_id, sample_body_comp)
        assert len(samples) == 3  # weight, body_fat, BMI

    def test_build_body_comp_samples_missing_timestamp(self, garmin_247: Garmin247Data) -> None:
        """Test _build_body_comp_samples returns empty for missing timestamp."""
        user_id = uuid4()
        samples = garmin_247._build_body_comp_samples(user_id, {"weightInGrams": 75000})
        assert samples == []

    def test_build_hrv_samples(self, garmin_247: Garmin247Data) -> None:
        """Test _build_hrv_samples returns samples without DB call."""
        user_id = uuid4()
        hrv_data = {
            "summaryId": "hrv-123",
            "startTimeInSeconds": 1768340715,
            "lastNightAvg": 84,
            "hrvValues": {"265": 70, "565": 73},
        }
        samples = garmin_247._build_hrv_samples(user_id, hrv_data)
        assert len(samples) == 3  # 1 avg + 2 values

    def test_build_stress_samples(self, garmin_247: Garmin247Data) -> None:
        """Test _build_stress_samples returns samples without DB call."""
        user_id = uuid4()
        stress_data = {
            "startTimeInSeconds": 1705276800,
            "stressLevelValues": {"0": 25, "300": 30, "600": -1},  # -1 is skipped
            "bodyBatteryValues": {"0": 80, "300": 78},
        }
        samples = garmin_247._build_stress_samples(user_id, stress_data)
        assert len(samples) == 4  # 2 stress + 2 battery

    def test_build_sleep_record(self, garmin_247: Garmin247Data, sample_sleep: dict[str, Any]) -> None:
        """Test _build_sleep_record returns record + detail without DB call."""
        user_id = uuid4()
        normalized = garmin_247.normalize_sleep(sample_sleep, user_id)
        result = garmin_247._build_sleep_record(user_id, normalized)

        assert result is not None
        record, detail = result
        assert record.category == "sleep"
        assert record.type == "sleep_session"
        assert detail.sleep_deep_minutes == 120  # 7200 / 60

    def test_build_activity_record(self, garmin_247: Garmin247Data) -> None:
        """Test _build_activity_record returns record + detail without DB call."""
        user_id = uuid4()
        activity = {
            "activityId": 123456,
            "startTimeInSeconds": 1705309200,
            "durationInSeconds": 3600,
            "activityType": "RUNNING",
            "distanceInMeters": 5000,
            "activeKilocalories": 350,
        }
        result = garmin_247._build_activity_record(user_id, activity)

        assert result is not None
        record, detail = result
        assert record.category == "workout"
        assert record.type == "running"
        assert detail.distance == Decimal("5000")

    def test_build_activity_record_missing_id(self, garmin_247: Garmin247Data) -> None:
        """Test _build_activity_record returns None for missing activityId."""
        user_id = uuid4()
        result = garmin_247._build_activity_record(user_id, {"startTimeInSeconds": 1705309200})
        assert result is None

    def test_build_moveiq_record(self, garmin_247: Garmin247Data) -> None:
        """Test _build_moveiq_record returns record without DB call."""
        user_id = uuid4()
        moveiq = {
            "startTimeInSeconds": 1705309200,
            "durationInSeconds": 600,
            "activityType": "WALKING",
            "summaryId": "moveiq_123",
        }
        record = garmin_247._build_moveiq_record(user_id, moveiq)
        assert record is not None
        assert record.type == "moveiq_walking"
        assert record.category == "activity"

    def test_build_moveiq_record_missing_start(self, garmin_247: Garmin247Data) -> None:
        """Test _build_moveiq_record returns None for missing startTime."""
        user_id = uuid4()
        record = garmin_247._build_moveiq_record(user_id, {"activityType": "WALKING"})
        assert record is None

    # -------------------------------------------------------------------------
    # Batch Processing Tests
    # -------------------------------------------------------------------------

    @patch("app.repositories.data_point_series_repository.DataPointSeriesRepository.bulk_create")
    def test_process_items_batch_dailies(
        self,
        mock_bulk_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
        sample_daily: dict[str, Any],
    ) -> None:
        """Test batch processing multiple daily items in a single bulk_create."""
        user = UserFactory()
        daily2 = {**sample_daily, "summaryId": "daily_456", "calendarDate": "2024-01-16"}

        count = garmin_247.process_items_batch(db, user.id, "dailies", [sample_daily, daily2])

        # Should call bulk_create exactly once for all samples
        mock_bulk_create.assert_called_once()
        assert count > 0

    @patch("app.repositories.data_point_series_repository.DataPointSeriesRepository.bulk_create")
    def test_process_items_batch_stress(
        self,
        mock_bulk_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
    ) -> None:
        """Test batch processing multiple stress items."""
        user = UserFactory()
        items = [
            {"startTimeInSeconds": 1705276800, "stressLevelValues": {"0": 25, "300": 30}},
            {"startTimeInSeconds": 1705363200, "stressLevelValues": {"0": 40}},
        ]

        count = garmin_247.process_items_batch(db, user.id, "stressDetails", items)

        mock_bulk_create.assert_called_once()
        assert count == 3  # 2 + 1

    @patch("app.services.event_record_service.event_record_service.bulk_create")
    @patch("app.services.event_record_service.event_record_service.bulk_create_details")
    def test_process_items_batch_sleeps(
        self,
        mock_bulk_details: MagicMock,
        mock_bulk_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
        sample_sleep: dict[str, Any],
    ) -> None:
        """Test batch processing sleep items uses bulk_create for records."""
        user = UserFactory()
        sleep2 = {**sample_sleep, "summaryId": "sleep_456"}

        # Make bulk_create return the actual record IDs that were passed in
        mock_bulk_create.side_effect = lambda db_session, records: [r.id for r in records]

        count = garmin_247.process_items_batch(db, user.id, "sleeps", [sample_sleep, sleep2])

        mock_bulk_create.assert_called_once()
        # Should create sleep details for inserted records
        mock_bulk_details.assert_called_once()
        assert count == 2

    def test_process_items_batch_empty(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test batch processing empty items returns 0."""
        user = UserFactory()
        count = garmin_247.process_items_batch(db, user.id, "dailies", [])
        assert count == 0

    @patch("app.repositories.data_point_series_repository.DataPointSeriesRepository.bulk_create")
    def test_process_items_batch_skips_bad_items(
        self,
        mock_bulk_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
    ) -> None:
        """Test batch processing skips invalid items and continues."""
        user = UserFactory()
        items = [
            {"startTimeInSeconds": 0},  # Missing timestamp -> skipped
            {"startTimeInSeconds": 1705276800, "stressLevelValues": {"0": 50}},  # Valid
        ]

        count = garmin_247.process_items_batch(db, user.id, "stressDetails", items)

        mock_bulk_create.assert_called_once()
        assert count == 1
