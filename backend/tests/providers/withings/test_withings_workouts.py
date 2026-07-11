from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.constants.workout_types.withings import get_unified_workout_type
from app.schemas.enums.workout_types import WorkoutType
from app.schemas.providers.withings import WithingsWorkout
from app.services.providers.withings.workouts import WithingsWorkouts


def test_category_mapping() -> None:
    assert get_unified_workout_type(1) == WorkoutType.WALKING
    assert get_unified_workout_type(2) == WorkoutType.RUNNING
    assert get_unified_workout_type(6) == WorkoutType.CYCLING
    assert get_unified_workout_type(999999) == WorkoutType.OTHER
    # Authoritative category ids from the spec.
    assert get_unified_workout_type(12) == WorkoutType.TENNIS
    assert get_unified_workout_type(15) == WorkoutType.BADMINTON
    assert get_unified_workout_type(16) == WorkoutType.STRENGTH_TRAINING
    assert get_unified_workout_type(17) == WorkoutType.STRENGTH_TRAINING
    assert get_unified_workout_type(18) == WorkoutType.ELLIPTICAL
    assert get_unified_workout_type(36) == WorkoutType.OTHER
    assert get_unified_workout_type(187) == WorkoutType.ROWING
    assert get_unified_workout_type(272) == WorkoutType.MULTISPORT
    assert get_unified_workout_type(308) == WorkoutType.INDOOR_CYCLING


def test_category_mapping_spec_extension() -> None:
    """Categories from the official OpenAPI spec (workout_object.category table)
    that have an exact unified WorkoutType equivalent."""
    assert get_unified_workout_type(306) == WorkoutType.WALKING  # Indoor walk
    assert get_unified_workout_type(455) == WorkoutType.STAND_UP_PADDLEBOARDING
    assert get_unified_workout_type(456) == WorkoutType.PADEL
    assert get_unified_workout_type(494) == WorkoutType.KAYAKING
    assert get_unified_workout_type(496) == WorkoutType.SAILING
    assert get_unified_workout_type(498) == WorkoutType.TRAIL_RUNNING
    assert get_unified_workout_type(510) == WorkoutType.PICKLEBALL
    assert get_unified_workout_type(521) == WorkoutType.TRIATHLON
    assert get_unified_workout_type(523) == WorkoutType.MOUNTAIN_BIKING
    assert get_unified_workout_type(529) == WorkoutType.BACKCOUNTRY_SKIING
    assert get_unified_workout_type(547) == WorkoutType.INDOOR_CYCLING  # Spinclass
    assert get_unified_workout_type(548) == WorkoutType.CRICKET
    assert get_unified_workout_type(551) == WorkoutType.MEDITATION
    assert get_unified_workout_type(552) == WorkoutType.STRETCHING
    assert get_unified_workout_type(557) == WorkoutType.LACROSSE
    # Lifestyle/chore categories (545 Chores, 554 Cleaning, 568 Cooking, …)
    # deliberately stay unmapped → OTHER.
    assert get_unified_workout_type(545) == WorkoutType.OTHER
    assert get_unified_workout_type(568) == WorkoutType.OTHER


def _make_workouts() -> WithingsWorkouts:
    return WithingsWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="withings",
        api_base_url="https://wbsapi.withings.net",
        oauth=MagicMock(),
    )


def test_normalize_workout_builds_event_record() -> None:
    w = _make_workouts()
    start = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    raw = WithingsWorkout.model_validate(
        {
            "id": 77,
            "category": 2,
            "startdate": start,
            "enddate": end,
            "data": {"steps": 5000, "calories": 300, "hr_average": 145},
        }
    )
    record, detail = w._normalize_workout(raw, uuid4())
    assert record.category == "workout"
    assert record.type == WorkoutType.RUNNING.value
    assert record.duration_seconds == 45 * 60
    assert record.external_id == "77"
    assert record.source == "withings"
    assert detail.record_id == record.id


@patch("app.services.providers.withings.workouts.event_record_service")
@patch.object(WithingsWorkouts, "get_workouts_from_api")
def test_load_data_saves_workouts(mock_api: MagicMock, mock_event: MagicMock) -> None:
    w = _make_workouts()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    mock_api.return_value = [
        {"id": 77, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    ]
    assert w.load_data(db, uuid4()) == 1
    mock_event.create.assert_called_once()
    mock_event.create_detail.assert_called_once()


@patch("app.services.providers.withings.workouts.event_record_service")
@patch.object(WithingsWorkouts, "get_workouts_from_api")
def test_load_data_skips_imported_workout_without_deviceid(mock_api: MagicMock, mock_event: MagicMock) -> None:
    """Workouts with no ``deviceid`` are foreign-aggregated echoes (e.g. via Health
    Connect) and are skipped; only Withings-hardware workouts are persisted."""
    w = _make_workouts()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    imported_null = {"id": 1, "category": 2, "startdate": start, "enddate": end, "deviceid": None, "data": {}}
    imported_absent = {"id": 2, "category": 2, "startdate": start, "enddate": end, "data": {}}
    native = {"id": 3, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    mock_api.return_value = [imported_null, imported_absent, native]

    assert w.load_data(db, uuid4()) == 1
    mock_event.create.assert_called_once()
    mock_event.create_detail.assert_called_once()


def test_normalize_workout_rejects_inverted_window() -> None:
    """A payload whose ``enddate`` precedes ``startdate`` yields a negative
    duration; it must be rejected, not persisted with an invalid duration."""
    w = _make_workouts()
    start = int(datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())  # 1h *before* start
    raw = WithingsWorkout.model_validate({"id": 5, "category": 2, "startdate": start, "enddate": end, "data": {}})
    with pytest.raises(ValueError, match="enddate must be after startdate"):
        w._normalize_workout(raw, uuid4())


@patch("app.services.providers.withings.workouts.event_record_service")
@patch.object(WithingsWorkouts, "get_workouts_from_api")
def test_load_data_skips_inverted_window_workout(mock_api: MagicMock, mock_event: MagicMock) -> None:
    """The negative-duration guard is honoured end-to-end: an inverted-window
    row is dropped while a valid neighbour still persists."""
    w = _make_workouts()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    inverted = {"id": 9, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    good = {
        "id": 10,
        "category": 2,
        "startdate": int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp()),
        "enddate": int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp()),
        "deviceid": "abc123",
        "data": {},
    }
    mock_api.return_value = [inverted, good]
    assert w.load_data(db, uuid4()) == 1
    mock_event.create.assert_called_once()


@patch("app.services.providers.withings.workouts.event_record_service")
@patch.object(WithingsWorkouts, "get_workouts_from_api")
def test_load_data_rolls_back_on_save_failure(mock_api: MagicMock, mock_event: MagicMock) -> None:
    """A persistence error on one workout rolls back the session and continues
    with the next, so a single bad write can't poison the whole batch."""
    w = _make_workouts()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    failing = {"id": 1, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    good = {"id": 2, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    mock_api.return_value = [failing, good]
    # First create() blows up mid-batch; the second succeeds.
    mock_event.create.side_effect = [Exception("db down"), MagicMock(id=uuid4())]

    assert w.load_data(db, uuid4()) == 1
    db.rollback.assert_called_once()
    assert mock_event.create.call_count == 2


@patch("app.services.providers.withings.workouts.event_record_service")
@patch.object(WithingsWorkouts, "get_workouts_from_api")
def test_load_data_skips_bad_workout(mock_api: MagicMock, mock_event: MagicMock) -> None:
    w = _make_workouts()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 15, 7, 45, tzinfo=timezone.utc).timestamp())
    # First workout is malformed (missing "category" and "startdate") so _normalize_workout raises.
    bad_workout = {"id": 99, "enddate": end, "deviceid": "abc123", "data": {}}
    good_workout = {"id": 77, "category": 2, "startdate": start, "enddate": end, "deviceid": "abc123", "data": {}}
    mock_api.return_value = [bad_workout, good_workout]
    assert w.load_data(db, uuid4()) == 1
    mock_event.create.assert_called_once()
    mock_event.create_detail.assert_called_once()


# ---------------------------------------------------------------------------
# Generic ISO start_date/end_date must be translated to ymd
# ---------------------------------------------------------------------------


@patch("app.services.providers.withings.workouts.paginate")
def test_load_data_with_iso_dates_passes_ymd_to_paginate(mock_paginate: MagicMock) -> None:
    """The sync task emits ISO start_date/end_date; they must reach paginate as
    startdateymd/enddateymd, not be dropped when the generic keys are used."""
    mock_paginate.return_value = []
    w = _make_workouts()
    db = MagicMock()
    user_id = uuid4()

    w.load_data(db, user_id, start_date="2024-01-01T00:00:00+00:00", end_date="2024-01-08T00:00:00+00:00")

    assert mock_paginate.called, "paginate was not called"
    _, kwargs = mock_paginate.call_args
    passed_params = kwargs.get("params", {})
    assert kwargs["service_path"] == "/v2/measure"
    assert kwargs["action"] == "getworkouts"
    assert kwargs["list_key"] == "series"
    assert passed_params["data_fields"] == "calories,steps,distance,hr_average,hr_min,hr_max,elevation"
    assert passed_params.get("startdateymd") == "2024-01-01", (
        f"Expected startdateymd='2024-01-01', got {passed_params.get('startdateymd')!r}"
    )
    assert passed_params.get("enddateymd") == "2024-01-08", (
        f"Expected enddateymd='2024-01-08', got {passed_params.get('enddateymd')!r}"
    )


@patch("app.services.providers.withings.workouts.paginate")
def test_get_workouts_uses_exact_ymd_window_by_default(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    w = _make_workouts()
    w.get_workouts_from_api(
        MagicMock(),
        uuid4(),
        start_date=datetime(2018, 7, 2, tzinfo=timezone.utc).isoformat(),
        end_date=datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc).isoformat(),
    )
    params = mock_paginate.call_args.kwargs["params"]
    assert params["startdateymd"] == "2018-07-02"
    assert params["enddateymd"] == "2018-07-02"


@patch("app.services.providers.withings.workouts.paginate")
def test_get_workouts_can_widen_ymd_window_for_webhook_notify(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    w = _make_workouts()
    w.get_workouts_from_api(
        MagicMock(),
        uuid4(),
        start_date=datetime(2018, 7, 2, tzinfo=timezone.utc).isoformat(),
        end_date=datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc).isoformat(),
        widen_ymd_window=True,
    )
    params = mock_paginate.call_args.kwargs["params"]
    assert params["startdateymd"] == "2018-07-01"
    assert params["enddateymd"] == "2018-07-03"


def test_to_ymd_converts_iso_string() -> None:
    """_to_ymd correctly parses ISO 8601 strings including timezone offsets."""
    assert WithingsWorkouts._to_ymd("2024-01-01T00:00:00+00:00") == "2024-01-01"
    assert WithingsWorkouts._to_ymd("2024-03-15T12:30:00Z") == "2024-03-15"


def test_to_ymd_converts_datetime_object() -> None:
    dt = datetime(2024, 6, 20, 8, 0, tzinfo=timezone.utc)
    assert WithingsWorkouts._to_ymd(dt) == "2024-06-20"


def test_to_ymd_returns_none_for_falsy() -> None:
    assert WithingsWorkouts._to_ymd(None) is None
    assert WithingsWorkouts._to_ymd("") is None


def test_to_ymd_returns_none_for_unparseable() -> None:
    assert WithingsWorkouts._to_ymd("not-a-date") is None
