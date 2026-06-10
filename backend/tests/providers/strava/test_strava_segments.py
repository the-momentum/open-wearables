"""Tests for Strava lap/split → workout segments mapping (#1076)."""

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.constants.workout_segments import SegmentKind
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.workouts import StravaWorkouts

_SINGLE_LAP = [{"lap_index": 1, "distance": 15354.1, "elapsed_time": 4327}]

_MANUAL_LAPS = [
    {
        "lap_index": 1,
        "distance": 400.0,
        "elapsed_time": 90,
        "moving_time": 90,
        "average_speed": 4.44,
        "average_heartrate": 150.0,
        "max_heartrate": 168.0,
        "average_watts": 280.0,
    },
    {"lap_index": 2, "distance": 200.0, "elapsed_time": 75, "average_heartrate": 130.0},
    {"lap_index": 3, "distance": 400.0, "elapsed_time": 88, "average_heartrate": 152.0},
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


def _activity(**overrides: Any) -> StravaActivityJSON:
    base = {
        "id": 98765,
        "name": "Morning Run",
        "type": "Run",
        "sport_type": "Run",
        "start_date": "2024-01-15T08:00:00Z",
        "elapsed_time": 3600,
        "utc_offset": 3600.0,
    }
    return StravaActivityJSON(**{**base, **overrides})


@pytest.fixture
def strava_workouts() -> StravaWorkouts:
    return StravaWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="strava",
        api_base_url="https://www.strava.com",
        oauth=MagicMock(),
    )


def test_segments_use_auto_km_splits_when_no_manual_laps(strava_workouts: StravaWorkouts) -> None:
    """A single (whole-activity) lap → segments come from the auto per-km splits, kind=lap."""
    segments = strava_workouts._build_segments(_activity(laps=_SINGLE_LAP, splits_metric=_SPLITS))
    assert segments is not None
    assert len(segments) == 2
    assert all(s.kind == SegmentKind.LAP for s in segments)
    assert segments[0].index == 1
    assert segments[0].distance_meters == 1001.9
    assert segments[0].duration_seconds == 349
    assert segments[0].average_heartrate == 127.5


def test_segments_prefer_manual_laps_when_set(strava_workouts: StravaWorkouts) -> None:
    """Multiple manual/device laps win over auto splits (kind=lap), carrying power."""
    segments = strava_workouts._build_segments(_activity(laps=_MANUAL_LAPS, splits_metric=_SPLITS))
    assert segments is not None
    assert len(segments) == 3
    assert all(s.kind == SegmentKind.LAP for s in segments)
    assert segments[0].distance_meters == 400.0
    assert segments[0].max_heartrate == 168
    assert segments[0].average_watts == 280.0


def test_segments_none_without_laps_or_splits(strava_workouts: StravaWorkouts) -> None:
    """No laps and no splits → no segments."""
    assert strava_workouts._build_segments(_activity()) is None


def test_normalize_workout_attaches_segments(strava_workouts: StravaWorkouts) -> None:
    """_normalize_workout puts the lap segments on the detail."""
    _record, detail = strava_workouts._normalize_workout(_activity(laps=_SINGLE_LAP, splits_metric=_SPLITS), uuid4())
    assert detail.segments is not None
    assert len(detail.segments) == 2
    assert detail.segments[0].kind == SegmentKind.LAP
