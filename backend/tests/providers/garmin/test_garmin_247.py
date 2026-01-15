"""Tests for Garmin 247 data implementation."""

from datetime import datetime, timezone
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
            "remSleepDurationInSeconds": 5400,  # 1.5 hours
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

    @patch("app.repositories.data_point_series_repository.DataPointSeriesRepository.create")
    def test_save_body_composition(
        self,
        mock_create: MagicMock,
        garmin_247: Garmin247Data,
        db: Session,
        sample_body_comp: dict[str, Any],
    ) -> None:
        """Test saving body composition data."""
        user_id = uuid4()

        count = garmin_247.save_body_composition(db, user_id, sample_body_comp)

        # Should create 3 data points: weight, body_fat, BMI
        assert mock_create.call_count == 3
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

    def test_load_and_save_all_default_dates(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all triggers backfill with default date range."""
        user = UserFactory()

        with (
            patch("app.integrations.celery.tasks.garmin_backfill_task.start_backfill") as mock_start_backfill,
            patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger,
        ):
            mock_trigger.return_value = {
                "triggered": ["sleeps"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            results = garmin_247.load_and_save_all(db, user.id)

            assert results["backfill_triggered"] is True
            assert "sleeps" in results["triggered_types"]
            mock_start_backfill.assert_called_once()

    def test_load_and_save_all_custom_dates(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all with custom date range."""
        user = UserFactory()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 7, tzinfo=timezone.utc)

        with (
            patch("app.integrations.celery.tasks.garmin_backfill_task.start_backfill"),
            patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger,
        ):
            mock_trigger.return_value = {
                "triggered": ["sleeps"],
                "failed": {},
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }

            results = garmin_247.load_and_save_all(db, user.id, start_time=start, end_time=end)

            # Verify custom dates were used
            mock_trigger.assert_called_once()
            call_kwargs = mock_trigger.call_args[1]
            assert call_kwargs["start_time"] == start
            assert call_kwargs["end_time"] == end

            assert results["backfill_triggered"] is True

    def test_load_and_save_all_string_dates(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all with ISO string dates."""
        user = UserFactory()

        with (
            patch("app.integrations.celery.tasks.garmin_backfill_task.start_backfill"),
            patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger,
        ):
            mock_trigger.return_value = {
                "triggered": ["sleeps"],
                "failed": {},
                "start_time": "2024-01-01T00:00:00+00:00",
                "end_time": "2024-01-07T00:00:00+00:00",
            }

            results = garmin_247.load_and_save_all(
                db,
                user.id,
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-07T00:00:00Z",
            )

            assert results["backfill_triggered"] is True

    def test_load_and_save_all_handles_errors(self, garmin_247: Garmin247Data, db: Session) -> None:
        """Test load_and_save_all handles errors from backfill service."""
        user = UserFactory()

        with (
            patch("app.integrations.celery.tasks.garmin_backfill_task.start_backfill"),
            patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger,
        ):
            mock_trigger.return_value = {
                "triggered": [],
                "failed": {"sleeps": "API Error"},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            results = garmin_247.load_and_save_all(db, user.id)

            # Should still return with backfill_triggered
            assert results["backfill_triggered"] is True
            assert results["triggered_types"] == []
            assert "sleeps" in results["failed_types"]

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
