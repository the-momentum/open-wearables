"""Withings payload normalization for measures, activity and workouts."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.enums import SeriesType
from app.schemas.enums.workout_types import WorkoutType
from app.schemas.providers.withings import WithingsWorkout
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.workouts import WithingsWorkouts


def _data_247() -> Withings247Data:
    return Withings247Data(provider_name="withings", api_base_url="https://wbsapi.withings.net", oauth=MagicMock())


def _workouts() -> WithingsWorkouts:
    return WithingsWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="withings",
        api_base_url="https://wbsapi.withings.net",
        oauth=MagicMock(),
    )


# ---------------------------- measures ----------------------------


def test_measure_group_scales_values_and_maps_known_types() -> None:
    groups = [
        {
            "grpid": 77,
            "date": 1_700_000_000,
            "timezone": "Europe/Paris",
            "measures": [
                {"value": 7500, "type": 1, "unit": -2},  # weight, kg
                {"value": 180, "type": 4, "unit": -2},  # height, metres -> cm
                {"value": 999, "type": 12, "unit": 0},  # deferred, no mapping
            ],
        }
    ]

    samples = _data_247().normalize_measures(groups, uuid4())

    by_type = {sample.series_type: sample for sample in samples}
    assert by_type[SeriesType.weight].value == Decimal("75.00")
    assert by_type[SeriesType.height].value == Decimal("180.00")
    assert SeriesType.body_temperature not in by_type
    assert by_type[SeriesType.weight].external_id == "77"
    assert by_type[SeriesType.weight].zone_offset == "+01:00"


def test_measure_group_falls_back_to_the_response_timezone() -> None:
    groups = [{"date": 1_700_000_000, "measures": [{"value": 7500, "type": 1, "unit": -2}]}]

    samples = _data_247().normalize_measures(groups, uuid4(), default_timezone="Europe/Paris")

    assert samples[0].zone_offset == "+01:00"


def test_a_malformed_measure_group_does_not_drop_the_batch() -> None:
    groups = [
        {"measures": [{"value": 1, "type": 1, "unit": 0}]},  # no date
        {"date": 1_700_000_000, "measures": [{"value": 7500, "type": 1, "unit": -2}]},
    ]

    samples = _data_247().normalize_measures(groups, uuid4())

    assert [sample.value for sample in samples] == [Decimal("75.00")]


# ---------------------------- daily activity ----------------------------


def test_activity_row_maps_fields_and_derives_passive_calories() -> None:
    rows = [
        {
            "date": "2026-03-01",
            "timezone": "Europe/Paris",
            "brand": 1,
            "steps": 8000,
            "distance": 6400.5,
            "calories": 400.0,
            "totalcalories": 2200.0,
        }
    ]

    samples = _data_247().normalize_activity(rows, uuid4())

    by_type = {sample.series_type: sample for sample in samples}
    assert by_type[SeriesType.steps].value == Decimal("8000")
    assert by_type[SeriesType.distance_walking_running].value == Decimal("6400.5")
    assert by_type[SeriesType.energy].value == Decimal("400.0")
    assert by_type[SeriesType.basal_energy].value == Decimal("1800.0")
    assert by_type[SeriesType.steps].is_daily_total is True


def test_externally_sourced_activity_is_dropped() -> None:
    # brand 18 is Withings' code for a re-imported external source; counting it
    # would double the origin connector the user may have linked directly.
    rows = [{"date": "2026-03-01", "brand": 18, "steps": 8000}]

    assert _data_247().normalize_activity(rows, uuid4()) == []


# ---------------------------- workouts ----------------------------


def test_workout_normalizes_into_a_record_and_detail() -> None:
    workout = WithingsWorkout.model_validate(
        {
            "id": 9001,
            "category": 2,
            "startdate": 1_700_000_000,
            "enddate": 1_700_003_600,
            "timezone": "Europe/Paris",
            "data": {"calories": 500.0, "steps": 6000, "distance": 5000.0, "hr_average": 150, "hr_max": 178},
        }
    )

    record, detail = _workouts()._normalize_workout(workout, uuid4())

    assert record.type == WorkoutType.RUNNING.value
    assert record.duration_seconds == 3600
    assert record.external_id == "9001"
    assert record.zone_offset == "+01:00"
    assert detail.heart_rate_avg == Decimal("150")
    assert detail.energy_burned == Decimal("500.0")


def test_unknown_workout_category_falls_back_to_other() -> None:
    workout = WithingsWorkout.model_validate({"category": 99999, "startdate": 1_700_000_000, "enddate": 1_700_000_600})

    record, _ = _workouts()._normalize_workout(workout, uuid4())

    assert record.type == WorkoutType.OTHER.value


@patch("app.services.providers.withings.workouts.paginate")
def test_workout_window_widens_by_a_local_day_on_each_edge(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = MagicMock(rows=[])

    _workouts().get_workouts_from_api(MagicMock(), uuid4(), startdateymd="2026-03-02", enddateymd="2026-03-04")

    # getworkouts keys on the user's local day, so a UTC window can clip an edge.
    params = mock_paginate.call_args.kwargs["params"]
    assert params["startdateymd"] == "2026-03-01"
    assert params["enddateymd"] == "2026-03-05"
