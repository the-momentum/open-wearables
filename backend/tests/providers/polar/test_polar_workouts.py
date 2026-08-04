"""
Tests for Polar workouts implementation.

Tests the PolarWorkouts class for fetching and processing workout data from Polar API.
"""

from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.constants.workout_types.polar import get_unified_workout_type
from app.schemas.enums import WorkoutType
from app.schemas.providers.polar import ExerciseJSON as PolarExerciseJSON
from app.services.providers.polar.workouts import PolarWorkouts
from tests.factories import UserConnectionFactory, UserFactory
from tests.fixtures.fit_builder import make_running_fit


class TestPolarWorkoutsInitialization:
    """Tests for PolarWorkouts initialization."""

    def test_polar_workouts_initialization(self, db: Session) -> None:
        """Test PolarWorkouts initializes with required dependencies."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Assert
        assert workouts is not None
        assert workouts.provider_name == "polar"
        assert workouts.api_base_url == "https://www.polaraccesslink.com"
        assert workouts.oauth is oauth


class TestPolarWorkoutsDateExtraction:
    """Tests for Polar-specific date extraction with UTC offset."""

    def test_extract_dates_with_offset_positive_offset(self, db: Session) -> None:
        """Test extracting dates with positive UTC offset."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act
        start_date, end_date = workouts._extract_dates_with_offset(
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,  # +1 hour
            duration="PT1H0M0S",  # 1 hour
        )

        # Assert
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert end_date > start_date
        assert (end_date - start_date).total_seconds() == 3600  # 1 hour

    def test_extract_dates_with_offset_negative_offset(self, db: Session) -> None:
        """Test extracting dates with negative UTC offset."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act
        start_date, end_date = workouts._extract_dates_with_offset(
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=-300,  # -5 hours
            duration="PT30M0S",  # 30 minutes
        )

        # Assert
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert (end_date - start_date).total_seconds() == 1800  # 30 minutes

    def test_extract_dates_not_implemented_fallback(self, db: Session) -> None:
        """Test that _extract_dates raises NotImplementedError for Polar."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act & Assert
        with pytest.raises(NotImplementedError):
            workouts._extract_dates("2024-01-15T08:00:00", "2024-01-15T09:00:00")


class TestPolarWorkoutsMetricsBuilding:
    """Tests for building metrics from Polar exercise data."""

    def test_build_metrics_with_heart_rate_data(self, db: Session, sample_polar_exercise: dict) -> None:
        """Test building metrics with complete heart rate data."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(**sample_polar_exercise)

        # Act
        metrics = workouts._build_metrics(exercise)

        # Assert
        assert metrics["heart_rate_avg"] == Decimal("145")
        assert metrics["heart_rate_max"] == 175
        assert metrics["energy_burned"] == Decimal("650")
        assert metrics["distance"] == Decimal("10000")

    def test_build_metrics_without_heart_rate_data(self, db: Session) -> None:
        """Test building metrics when heart rate data is missing."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(
            id="ABC123",
            device="Polar Vantage V2",
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,
            duration="PT1H0M0S",
            sport="RUNNING",
            detailed_sport_info="RUNNING",
        )

        # Act
        metrics = workouts._build_metrics(exercise)

        # Assert
        assert metrics["heart_rate_avg"] is None
        assert metrics["heart_rate_max"] is None


class TestPolarWorkoutsNormalization:
    """Tests for normalizing Polar exercises to event records."""

    def test_normalize_workout_complete_data(self, db: Session, sample_polar_exercise: dict) -> None:
        """Test normalizing workout with complete data."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(**sample_polar_exercise)

        # Act
        record, detail = workouts._normalize_workout(exercise, user.id)

        # Assert
        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.source_name == "Polar Vantage V2"
        assert record.device_model == "Polar Vantage V2"
        assert record.duration_seconds == 3600
        assert record.external_id == "ABC123"
        assert record.user_id == user.id
        assert detail.heart_rate_avg == Decimal("145")
        assert detail.heart_rate_max == 175

    def test_normalize_workout_workout_type_mapping(self, db: Session) -> None:
        """Test workout type is correctly mapped from Polar sport type."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Test cycling
        exercise = PolarExerciseJSON(
            id="CYC123",
            device="Polar Vantage V2",
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,
            duration="PT1H0M0S",
            sport="CYCLING",
            detailed_sport_info="CYCLING_ROAD",
        )

        # Act
        record, detail = workouts._normalize_workout(exercise, user.id)

        # Assert
        assert record.type == WorkoutType.CYCLING.value


class TestPolarWorkoutsAPIRequests:
    """Tests for API request methods."""

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workouts_from_api_default_params(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting workouts with default parameters."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        workouts.get_workouts_from_api(db, user.id)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["endpoint"] == "/v3/exercises"
        assert call_kwargs["params"]["samples"] == "false"
        assert call_kwargs["params"]["zones"] == "false"
        assert call_kwargs["params"]["route"] == "false"

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workouts_from_api_with_options(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting workouts with samples, zones, and route enabled."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        workouts.get_workouts_from_api(db, user.id, samples=True, zones=True, route=True)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["samples"] == "true"
        assert call_kwargs["params"]["zones"] == "true"
        assert call_kwargs["params"]["route"] == "true"

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workout_detail_from_api(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting detailed workout data for specific exercise."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = {}
        workout_id = "ABC123"

        # Act
        workouts.get_workout_detail_from_api(db, user.id, workout_id, samples=True)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert f"/v3/exercises/{workout_id}" in call_kwargs["endpoint"]
        assert call_kwargs["params"]["samples"] == "true"


class TestPolarWorkoutsDataLoading:
    """Tests for loading workout data from Polar API."""

    @patch("app.services.providers.polar.workouts.download_binary_content")
    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    def test_load_data_success(
        self,
        mock_create_detail: MagicMock,
        mock_create: MagicMock,
        mock_request: MagicMock,
        mock_download: MagicMock,
        db: Session,
        sample_polar_exercise: dict,
    ) -> None:
        """Test successful data loading from Polar API."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = [sample_polar_exercise]
        mock_download.return_value = b""  # no FIT available — summary ingestion only

        # Act
        result = workouts.load_data(db, user.id)

        # Assert
        assert result == 1
        mock_create.assert_called_once()
        mock_create_detail.assert_called_once()

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_load_data_empty_response(self, mock_request: MagicMock, db: Session) -> None:
        """Test loading data when API returns empty list."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        result = workouts.load_data(db, user.id)

        # Assert
        assert result == 0


@pytest.fixture
def no_fit_file_storage() -> Generator[MagicMock, None, None]:
    """Keep FIT ingestion tests off S3 for anyone running with STORE_FIT_FILES enabled."""
    with patch("app.services.providers.polar.workouts.store_fit_file") as mock_store:
        yield mock_store


@pytest.fixture
def polar_workouts() -> PolarWorkouts:
    """PolarWorkouts wired with the real repositories."""
    from app.models import EventRecord, User
    from app.repositories.event_record_repository import EventRecordRepository
    from app.repositories.user_connection_repository import UserConnectionRepository
    from app.repositories.user_repository import UserRepository
    from app.services.providers.polar.oauth import PolarOAuth

    connection_repo = UserConnectionRepository()
    oauth = PolarOAuth(
        user_repo=UserRepository(User),
        connection_repo=connection_repo,
        provider_name="polar",
        api_base_url="https://www.polaraccesslink.com",
    )
    return PolarWorkouts(
        workout_repo=EventRecordRepository(EventRecord),
        connection_repo=connection_repo,
        provider_name="polar",
        api_base_url="https://www.polaraccesslink.com",
        oauth=oauth,
    )


@pytest.mark.usefixtures("no_fit_file_storage")
class TestPolarExerciseFitIngestion:
    """Tests for the FIT enrichment step itself (_ingest_exercise_fit).

    A Polar exercise JSON is a summary: total duration, distance, avg/max HR. Laps,
    splits and pool lengths only exist in the FIT file the watch recorded, served at
    GET /v3/exercises/{id}/fit.
    """

    @staticmethod
    def _saved_fields(workouts: PolarWorkouts) -> dict:
        """The fields dict passed to update_workout_fields(db, record_id, fields)."""
        return workouts.event_record_detail_repo.update_workout_fields.call_args.args[2]

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_laps_are_saved_as_segments(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """Laps parsed out of the FIT file land in workout_details.segments."""
        # Arrange
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        polar_workouts.event_record_detail_repo.update_workout_fields.assert_called_once()
        segments = self._saved_fields(polar_workouts)["segments"]
        assert len(segments) == 2
        assert {s["kind"] for s in segments} == {"lap"}
        assert [s["index"] for s in segments] == [0, 1]
        assert all(s["avg_heart_rate"] > 0 for s in segments)
        assert all(s["elapsed_seconds"] > 0 for s in segments)
        assert all(s["distance_meters"] > 0 for s in segments)

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_fit_pulled_from_exercise_fit_endpoint(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """The FIT is fetched per exercise from AccessLink, keyed by Polar's exercise id."""
        # Arrange
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        assert mock_download.call_args.kwargs["url"] == "https://www.polaraccesslink.com/v3/exercises/ABC123/fit"
        assert mock_download.call_args.kwargs["provider_name"] == "polar"

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_raw_fit_is_offered_to_storage(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
        no_fit_file_storage: MagicMock,
    ) -> None:
        """The downloaded FIT is handed to raw storage, which no-ops unless enabled."""
        # Arrange
        fit_bytes = make_running_fit()
        mock_download.return_value = fit_bytes
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        no_fit_file_storage.assert_called_once()
        assert no_fit_file_storage.call_args.kwargs["fit_bytes"] == fit_bytes
        assert no_fit_file_storage.call_args.kwargs["activity_id"] == "ABC123"

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_download_failure_writes_nothing(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """AccessLink has no FIT for every exercise (manual entries, third-party uploads)."""
        # Arrange
        mock_download.side_effect = RuntimeError("404 Not Found")
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        polar_workouts.event_record_detail_repo.update_workout_fields.assert_not_called()

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_unparseable_fit_writes_nothing(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """Corrupt FIT bytes are swallowed — the exercise summary is already saved."""
        # Arrange
        mock_download.return_value = b"definitely not a FIT file"
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        polar_workouts.event_record_detail_repo.update_workout_fields.assert_not_called()

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_empty_body_writes_nothing(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """An empty response body is 'no FIT', not a parse failure."""
        # Arrange
        mock_download.return_value = b""
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        polar_workouts.event_record_detail_repo.update_workout_fields.assert_not_called()

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_missing_exercise_id_skips_download(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """Without Polar's exercise id there is no FIT URL to build."""
        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), None)

        # Assert
        mock_download.assert_not_called()

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_samples_skipped_when_flag_disabled(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """Segments are always saved; per-second samples stay behind the ingest flag."""
        # Arrange
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        with (
            patch("app.services.providers.polar.workouts.settings", ingest_workout_samples=False),
            patch("app.services.providers.polar.workouts.timeseries_service") as mock_timeseries,
        ):
            polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        mock_timeseries.bulk_create_samples.assert_not_called()
        assert self._saved_fields(polar_workouts)["segments"]

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_samples_ingested_when_flag_enabled(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """With the flag on, the FIT's per-second samples go to the timeseries service."""
        # Arrange
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        with (
            patch("app.services.providers.polar.workouts.settings", ingest_workout_samples=True),
            patch("app.services.providers.polar.workouts.timeseries_service") as mock_timeseries,
        ):
            polar_workouts._ingest_exercise_fit(db, uuid4(), uuid4(), "ABC123")

        # Assert
        mock_timeseries.bulk_create_samples.assert_called_once()
        samples = mock_timeseries.bulk_create_samples.call_args.args[1]
        assert samples
        assert {s.source for s in samples} == {"polar"}


@pytest.mark.usefixtures("no_fit_file_storage")
class TestPolarFitPersistence:
    """The segments write has to survive the transaction, not just reach the repository.

    update_workout_fields leaves the transaction open by contract and the exercise
    summary is committed before enrichment runs, so nothing downstream would commit
    these fields on our behalf.
    """

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_segments_are_committed(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """Laps are readable from the database after ingestion, via the real repository."""
        # Arrange
        from app.models import WorkoutDetails
        from tests.factories import WorkoutDetailsFactory

        details = WorkoutDetailsFactory()
        record_id = details.record_id
        db.commit()  # the exercise summary is committed before enrichment runs
        mock_download.return_value = make_running_fit()

        # Act
        polar_workouts._ingest_exercise_fit(db, uuid4(), record_id, "ABC123")

        # Assert — re-read rather than trusting the identity map
        db.expire_all()
        saved = db.get(WorkoutDetails, record_id)
        assert saved is not None
        assert saved.segments is not None
        assert len(saved.segments) == 2
        assert {s["kind"] for s in saved.segments} == {"lap"}

    @patch("app.services.providers.polar.workouts.download_binary_content")
    def test_failed_ingestion_leaves_session_usable(
        self,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
    ) -> None:
        """A bad FIT must not poison the transaction for the next exercise in the sync."""
        # Arrange
        from app.models import WorkoutDetails
        from tests.factories import WorkoutDetailsFactory

        broken = WorkoutDetailsFactory()
        healthy = WorkoutDetailsFactory()
        db.commit()  # both summaries are committed before enrichment runs
        mock_download.return_value = b"definitely not a FIT file"

        # Act — first exercise fails, second succeeds on the same session
        polar_workouts._ingest_exercise_fit(db, uuid4(), broken.record_id, "BROKEN")
        mock_download.return_value = make_running_fit()
        polar_workouts._ingest_exercise_fit(db, uuid4(), healthy.record_id, "ABC123")

        # Assert
        db.expire_all()
        assert db.get(WorkoutDetails, broken.record_id).segments is None
        assert len(db.get(WorkoutDetails, healthy.record_id).segments) == 2


@pytest.mark.usefixtures("no_fit_file_storage")
class TestPolarFitIngestionWiring:
    """Both exercise entry points — the pull sync and the EXERCISE webhook — enrich with FIT."""

    @patch("app.services.providers.polar.workouts.download_binary_content")
    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    @patch("app.services.event_record_service.event_record_service.create")
    def test_load_data_enriches_each_exercise(
        self,
        mock_create: MagicMock,
        mock_create_detail: MagicMock,
        mock_request: MagicMock,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
        sample_polar_exercise: dict,
    ) -> None:
        """The pull sync saves the summary and then the laps from the FIT file."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")
        mock_request.return_value = [sample_polar_exercise]
        mock_create.return_value = MagicMock(id=uuid4(), external_id=sample_polar_exercise["id"])
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        result = polar_workouts.load_data(db, user.id)

        # Assert
        assert result == 1
        saved_fields = polar_workouts.event_record_detail_repo.update_workout_fields.call_args.args[2]
        assert len(saved_fields["segments"]) == 2

    @patch("app.services.providers.polar.workouts.download_binary_content")
    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    @patch("app.services.event_record_service.event_record_service.create")
    def test_webhook_exercise_is_enriched(
        self,
        mock_create: MagicMock,
        mock_create_detail: MagicMock,
        mock_request: MagicMock,
        mock_download: MagicMock,
        db: Session,
        polar_workouts: PolarWorkouts,
        sample_polar_exercise: dict,
    ) -> None:
        """An EXERCISE webhook ping gets the same treatment as the pull sync."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")
        mock_request.return_value = sample_polar_exercise
        mock_create.return_value = MagicMock(id=uuid4(), external_id=sample_polar_exercise["id"])
        mock_download.return_value = make_running_fit()
        polar_workouts.event_record_detail_repo = MagicMock()

        # Act
        result = polar_workouts.fetch_and_save_exercise(db, user.id, "/v3/exercises/ABC123")

        # Assert
        assert result == 1
        saved_fields = polar_workouts.event_record_detail_repo.update_workout_fields.call_args.args[2]
        assert len(saved_fields["segments"]) == 2


class TestGetUnifiedWorkoutType:
    @pytest.mark.parametrize(
        ("sport", "detailed", "expected"),
        [
            ("CYCLING", "INDOOR_CYCLING", WorkoutType.INDOOR_CYCLING),
            ("OTHER", "JUMP_ROPE", WorkoutType.CARDIO_TRAINING),
            ("OTHER", "KICKBOXING_MARTIAL_ARTS", WorkoutType.BOXING),
        ],
    )
    def test_mappings(self, sport: str, detailed: str, expected: WorkoutType) -> None:
        assert get_unified_workout_type(sport, detailed) == expected
