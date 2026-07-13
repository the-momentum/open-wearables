"""Tests for Strava per-sample workout stream ingestion (#1050)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts

_START_DT = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
_ZONE_OFFSET = "+01:00"
_DEVICE_MODEL = "Forerunner 965"

_STRAVA_STREAMS_3S: dict[str, Any] = {
    "time": {"data": [0, 1, 2]},
    "heartrate": {"data": [120, 121, 122]},
    "velocity_smooth": {"data": [3.0, 3.1, 3.2]},
}

_SAMPLE_ACTIVITY = StravaActivityJSON(
    id=98765,
    name="Morning Run",
    type="Run",
    sport_type="Run",
    start_date="2024-01-15T08:00:00Z",
    elapsed_time=3600,
    utc_offset=3600.0,
    device_name=_DEVICE_MODEL,
)


@pytest.fixture
def strava_workouts() -> StravaWorkouts:
    """Minimal StravaWorkouts instance with mocked repos/oauth."""
    workout_repo = EventRecordRepository(EventRecord)
    connection_repo = UserConnectionRepository()
    oauth = StravaOAuth(
        user_repo=MagicMock(),
        connection_repo=connection_repo,
        provider_name="strava",
        api_base_url="https://www.strava.com",
    )
    return StravaWorkouts(
        workout_repo=workout_repo,
        connection_repo=connection_repo,
        provider_name="strava",
        api_base_url="https://www.strava.com",
        oauth=oauth,
    )


class TestBuildWorkoutSamples:
    """Unit tests for StravaWorkouts._build_workout_samples."""

    def test_happy_path_returns_correct_samples(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Happy path: streams with time+heartrate+velocity_smooth → correct samples."""
        user_id = uuid4()
        with patch.object(strava_workouts, "_make_api_request", return_value=_STRAVA_STREAMS_3S):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        assert len(samples) == 6

        hr_samples = [s for s in samples if s.series_type == SeriesType.heart_rate]
        speed_samples = [s for s in samples if s.series_type == SeriesType.speed]
        assert len(hr_samples) == 3
        assert len(speed_samples) == 3

    def test_happy_path_recorded_at_offsets(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """recorded_at = start_dt + time[i] seconds for each sample."""
        user_id = uuid4()
        with patch.object(strava_workouts, "_make_api_request", return_value=_STRAVA_STREAMS_3S):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        hr_samples = sorted(
            [s for s in samples if s.series_type == SeriesType.heart_rate],
            key=lambda s: s.recorded_at,
        )
        for i, sample in enumerate(hr_samples):
            assert sample.recorded_at == _START_DT + timedelta(seconds=i)

    def test_happy_path_series_type_and_value(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Correct series_type, value, source, zone_offset on each sample."""
        user_id = uuid4()
        with patch.object(strava_workouts, "_make_api_request", return_value=_STRAVA_STREAMS_3S):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        hr_samples = sorted(
            [s for s in samples if s.series_type == SeriesType.heart_rate],
            key=lambda s: s.recorded_at,
        )
        assert hr_samples[0].value == Decimal("120")
        assert hr_samples[1].value == Decimal("121")
        assert hr_samples[2].value == Decimal("122")

        speed_samples = sorted(
            [s for s in samples if s.series_type == SeriesType.speed],
            key=lambda s: s.recorded_at,
        )
        assert speed_samples[0].value == Decimal("3.0")

        for s in samples:
            assert s.source == "strava"
            assert s.device_model == _DEVICE_MODEL
            assert s.zone_offset == _ZONE_OFFSET
            assert s.user_id == user_id
            assert isinstance(s, TimeSeriesSampleCreate)

    def test_no_time_stream_returns_empty(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Streams dict without 'time' key → empty list."""
        user_id = uuid4()
        streams_no_time = {"heartrate": {"data": [120, 130]}}
        with patch.object(strava_workouts, "_make_api_request", return_value=streams_no_time):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        assert samples == []

    def test_empty_time_stream_returns_empty(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Empty 'time' data array → empty list."""
        user_id = uuid4()
        streams_empty_time: dict[str, Any] = {"time": {"data": []}, "heartrate": {"data": []}}
        with patch.object(strava_workouts, "_make_api_request", return_value=streams_empty_time):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        assert samples == []

    def test_non_dict_response_returns_empty(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Non-dict API response (e.g. list, None) → empty list, no crash."""
        user_id = uuid4()
        with patch.object(strava_workouts, "_make_api_request", return_value=[]):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)
        assert samples == []

    def test_metric_stream_shorter_than_time_guarded(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """metric data shorter than time → only valid indices emitted."""
        user_id = uuid4()
        streams: dict[str, Any] = {
            "time": {"data": [0, 1, 2]},
            "heartrate": {"data": [120]},
        }
        with patch.object(strava_workouts, "_make_api_request", return_value=streams):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        assert len(samples) == 1
        assert samples[0].value == Decimal("120")

    def test_distance_not_in_samples(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """distance stream is intentionally excluded (no generic SeriesType.distance)."""
        user_id = uuid4()
        streams: dict[str, Any] = {
            "time": {"data": [0, 1]},
            "distance": {"data": [0.0, 10.0]},
            "heartrate": {"data": [120, 130]},
        }
        with patch.object(strava_workouts, "_make_api_request", return_value=streams):
            samples = strava_workouts._build_workout_samples(db, user_id, 98765, _START_DT, _ZONE_OFFSET, _DEVICE_MODEL)

        assert all(s.series_type != SeriesType.distance for s in samples if hasattr(SeriesType, "distance"))
        assert all(s.series_type == SeriesType.heart_rate for s in samples)


class TestFlagGuard:
    """Ensure flag OFF prevents any Strava streams API call."""

    def test_flag_off_makes_no_api_call(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """When ingest_workout_samples is False, _make_api_request must NOT be called."""
        user_id = uuid4()
        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=False,
            ),
            patch.object(strava_workouts, "_make_api_request") as mock_api,
        ):
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, MagicMock())

        mock_api.assert_not_called()
        assert count == 0

    def test_flag_off_makes_no_save(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """When ingest_workout_samples is False, bulk_create_samples must NOT be called."""
        user_id = uuid4()
        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=False,
            ),
            patch("app.services.providers.strava.workouts.timeseries_service") as mock_ts,
        ):
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, MagicMock())

        mock_ts.bulk_create_samples.assert_not_called()
        assert count == 0


class TestIngestionWiring:
    """Integration-level tests for the wiring in _ingest_workout_streams."""

    def test_flag_on_calls_bulk_create_samples(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Flag ON: bulk_create_samples called with the built samples."""
        user_id = uuid4()
        record_mock = MagicMock()
        record_mock.start_datetime = _START_DT
        record_mock.zone_offset = _ZONE_OFFSET

        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=True,
            ),
            patch.object(strava_workouts, "_make_api_request", return_value=_STRAVA_STREAMS_3S),
            patch("app.services.providers.strava.workouts.timeseries_service") as mock_ts,
        ):
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, record_mock)

        mock_ts.bulk_create_samples.assert_called_once()
        call_args = mock_ts.bulk_create_samples.call_args
        saved_samples = call_args[0][1]
        assert len(saved_samples) == 6
        assert count == 6
        assert all(s.device_model == _DEVICE_MODEL for s in saved_samples)

    def test_save_raises_swallowed_returns_zero(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Persistence raising is swallowed; workout ingestion continues, 0 saved."""
        user_id = uuid4()
        record_mock = MagicMock()
        record_mock.start_datetime = _START_DT
        record_mock.zone_offset = _ZONE_OFFSET

        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=True,
            ),
            patch.object(strava_workouts, "_make_api_request", return_value=_STRAVA_STREAMS_3S),
            patch("app.services.providers.strava.workouts.timeseries_service") as mock_ts,
        ):
            mock_ts.bulk_create_samples.side_effect = RuntimeError("db write failure")
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, record_mock)

        assert count == 0

    def test_fetch_raises_swallowed_returns_zero(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Fetch raising an exception is swallowed; workout ingestion continues, 0 saved."""
        user_id = uuid4()
        record_mock = MagicMock()
        record_mock.start_datetime = _START_DT
        record_mock.zone_offset = _ZONE_OFFSET

        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=True,
            ),
            patch.object(
                strava_workouts,
                "_make_api_request",
                side_effect=RuntimeError("network failure"),
            ),
            patch("app.services.providers.strava.workouts.timeseries_service") as mock_ts,
        ):
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, record_mock)

        mock_ts.bulk_create_samples.assert_not_called()
        assert count == 0

    def test_empty_samples_no_save(
        self,
        strava_workouts: StravaWorkouts,
        db: Session,
    ) -> None:
        """Empty sample list (no time stream) → bulk_create_samples never called."""
        user_id = uuid4()
        record_mock = MagicMock()
        record_mock.start_datetime = _START_DT
        record_mock.zone_offset = _ZONE_OFFSET

        streams_no_time: dict[str, Any] = {"heartrate": {"data": [120]}}
        with (
            patch(
                "app.services.providers.strava.workouts.settings",
                ingest_workout_samples=True,
            ),
            patch.object(strava_workouts, "_make_api_request", return_value=streams_no_time),
            patch("app.services.providers.strava.workouts.timeseries_service") as mock_ts,
        ):
            count = strava_workouts._ingest_workout_streams(db, _SAMPLE_ACTIVITY, user_id, record_mock)

        mock_ts.bulk_create_samples.assert_not_called()
        assert count == 0
