"""Tests for Strava laps/splits -> workout segments mapping."""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import WorkoutDetails
from app.schemas.enums import EventCategory
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.event_record_service import event_record_service
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts
from tests.factories import UserFactory

_SINGLE_LAP = [
    {
        "lap_index": 1,
        "distance": 15354.1,
        "elapsed_time": 4327,
        "moving_time": 4200,
        "start_date": "2024-01-15T08:00:00Z",
    }
]

_MANUAL_LAPS = [
    {
        "lap_index": 1,
        "distance": 400.0,
        "elapsed_time": 90,
        "moving_time": 90,
        "start_date": "2024-01-15T08:00:00Z",
        "average_speed": 4.44,
        "average_heartrate": 150.0,
        "max_heartrate": 168.0,
        "average_cadence": 92.0,
        "average_watts": 280.0,
        "total_elevation_gain": 3.5,
    },
    {
        "lap_index": 2,
        "distance": 200.0,
        "elapsed_time": 75,
        "start_date": "2024-01-15T08:01:30Z",
        "average_heartrate": 130.0,
    },
    {
        "lap_index": 3,
        "distance": 400.0,
        "elapsed_time": 88,
        "start_date": "2024-01-15T08:02:45Z",
        "average_heartrate": 152.0,
    },
]

_SPLITS = [
    {
        "split": 1,
        "distance": 1001.9,
        "elapsed_time": 349,
        "moving_time": 330,
        "average_speed": 3.04,
        "average_heartrate": 127.5,
    },
    {
        "split": 2,
        "distance": 1000.0,
        "elapsed_time": 293,
        "moving_time": 293,
        "average_speed": 3.41,
        "average_heartrate": 142.0,
    },
]


class TestStravaSegments:
    @pytest.fixture
    def workouts(self) -> StravaWorkouts:
        oauth = StravaOAuth(
            user_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name="strava",
            api_base_url="https://www.strava.com/api/v3",
        )
        return StravaWorkouts(
            workout_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name="strava",
            api_base_url="https://www.strava.com/api/v3",
            oauth=oauth,
        )

    def _activity(self, **overrides: Any) -> StravaActivityJSON:
        base: dict[str, Any] = {
            "id": 98765,
            "name": "Morning Run",
            "type": "Run",
            "sport_type": "Run",
            "start_date": "2024-01-15T08:00:00Z",
            "elapsed_time": 3600,
        }
        return StravaActivityJSON(**{**base, **overrides})

    def test_segments_use_auto_km_splits_when_no_manual_laps(self, workouts: StravaWorkouts) -> None:
        """A single whole-activity lap is replaced by the auto per-km splits."""
        segments = workouts._build_segments(self._activity(laps=_SINGLE_LAP, splits_metric=_SPLITS))

        assert segments is not None
        assert len(segments) == 2
        assert all(s["kind"] == "lap" for s in segments)
        assert segments[0]["index"] == 0
        assert segments[0]["start_time"] == "2024-01-15T08:00:00+00:00"
        assert segments[1]["start_time"] == "2024-01-15T08:05:49+00:00"
        assert segments[0]["distance_meters"] == 1001.9
        assert segments[0]["elapsed_seconds"] == 349.0
        assert segments[0]["avg_speed"] == 3.04
        assert segments[0]["avg_heart_rate"] == 127.5

    def test_segments_prefer_manual_laps_when_set(self, workouts: StravaWorkouts) -> None:
        """Multiple manual/device laps win over auto splits and carry lap-only fields."""
        segments = workouts._build_segments(self._activity(laps=_MANUAL_LAPS, splits_metric=_SPLITS))

        assert segments is not None
        assert len(segments) == 3
        assert all(s["kind"] == "lap" for s in segments)
        assert segments[0]["index"] == 0
        assert segments[0]["start_time"] == "2024-01-15T08:00:00+00:00"
        assert segments[0]["distance_meters"] == 400.0
        assert segments[0]["elapsed_seconds"] == 90.0
        assert segments[0]["avg_heart_rate"] == 150.0
        assert segments[0]["max_heart_rate"] == 168.0
        assert segments[0]["avg_cadence"] == 92.0
        assert segments[0]["avg_power"] == 280.0
        assert segments[0]["total_ascent"] == 3.5
        # Absent metrics are dropped, not stored as null
        assert "avg_power" not in segments[1]

    def test_segments_none_without_laps_or_splits(self, workouts: StravaWorkouts) -> None:
        assert workouts._build_segments(self._activity()) is None

    def test_single_lap_without_splits_is_kept(self, workouts: StravaWorkouts) -> None:
        segments = workouts._build_segments(self._activity(laps=_SINGLE_LAP))

        assert segments is not None
        assert len(segments) == 1
        assert segments[0]["kind"] == "lap"
        assert segments[0]["distance_meters"] == 15354.1

    def test_normalize_workout_attaches_segments(self, workouts: StravaWorkouts) -> None:
        _record, detail = workouts._normalize_workout(self._activity(laps=_SINGLE_LAP, splits_metric=_SPLITS), uuid4())

        assert detail.segments is not None
        assert len(detail.segments) == 2
        assert detail.segments[0]["kind"] == "lap"

    def test_webhook_adds_segments_to_a_workout_stored_from_the_summary_list(
        self, workouts: StravaWorkouts, db: Session
    ) -> None:
        user_id = UUID(str(UserFactory().id))
        with (
            patch.object(workouts, "get_workouts", autospec=True, return_value=[self._activity()]),
            patch.object(workouts, "_ingest_workout_streams", autospec=True, return_value=0),
        ):
            workouts.load_data(db, user_id)
            # The second delivery is a webhook retry: it must not duplicate anything.
            for _ in range(2):
                (record_id,) = workouts.process_push_activity(
                    db, self._activity(laps=_MANUAL_LAPS, splits_metric=_SPLITS), user_id
                )

        stored = event_record_service.event_record_detail_repo.get_by_record_id(db, record_id, EventCategory.WORKOUT)
        assert isinstance(stored, WorkoutDetails)
        assert [s["distance_meters"] for s in stored.segments or []] == [400.0, 200.0, 400.0]
