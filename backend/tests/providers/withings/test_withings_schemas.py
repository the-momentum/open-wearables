import pytest
from pydantic import ValidationError

from app.schemas.providers.withings import (
    WithingsActivity,
    WithingsMeasureGroup,
    WithingsNotification,
    WithingsSleepSummary,
    WithingsWorkout,
)


def test_notification_parses_form_fields() -> None:
    n = WithingsNotification(userid="123", appli=1, startdate=1728000000, enddate=1728001000)
    assert n.userid == "123"
    assert n.appli == 1
    assert n.startdate == 1728000000
    assert n.enddate == 1728001000


def test_notification_allows_profile_change_shape() -> None:
    """appli 46 sends userid + action and no date range."""
    n = WithingsNotification(userid="123", appli=46, action="unlink")
    assert n.startdate is None
    assert n.enddate is None
    assert n.action == "unlink"


def test_measure_group_requires_date() -> None:
    """measuregrp_object: ingestion is impossible without the group timestamp."""
    with pytest.raises(ValidationError):
        WithingsMeasureGroup.model_validate({"measures": [{"value": 1, "type": 1, "unit": 0}]})


def test_measure_group_parses_nested_measures() -> None:
    group = WithingsMeasureGroup.model_validate(
        {
            "grpid": 12,
            "date": 1594245600,
            "category": 1,
            "deviceid": "892359876fd8805ac45bab078c4828692f0276b1",
            "measures": [{"value": 65750, "type": 1, "unit": -3}],
        }
    )
    assert group.measures[0].value == 65750
    assert group.measures[0].unit == -3
    assert group.deviceid is not None


def test_sleep_summary_tolerates_null_stage_durations() -> None:
    """Per spec, externally sourced nights null the light/deep/REM durations."""
    summary = WithingsSleepSummary.model_validate(
        {
            "id": 12345,
            "startdate": 1594245600,
            "enddate": 1594257200,
            "data": {
                "deepsleepduration": None,
                "lightsleepduration": None,
                "remsleepduration": None,
                "sleep_efficiency": 0.92,
            },
        }
    )
    assert summary.data.deepsleepduration is None
    assert summary.data.sleep_efficiency == 0.92


def test_sleep_summary_defaults_missing_data_object() -> None:
    summary = WithingsSleepSummary.model_validate({"startdate": 1, "enddate": 2})
    assert summary.data.deepsleepduration is None


def test_workout_accepts_float_metrics() -> None:
    """Spec types distance/calories as integer, but live payloads send doubles."""
    workout = WithingsWorkout.model_validate(
        {
            "id": 77,
            "category": 2,
            "startdate": 1594245600,
            "enddate": 1594257200,
            "deviceid": "abc",
            "data": {"distance": 12888.33, "calories": 300.5},
        }
    )
    assert workout.data.distance == 12888.33
    assert workout.data.calories == 300.5


def test_workout_requires_category_and_window() -> None:
    with pytest.raises(ValidationError):
        WithingsWorkout.model_validate({"id": 1, "enddate": 2})


def test_activity_carries_spec_origin_signals() -> None:
    """brand (1=Withings, 18=external) and is_tracker come straight from the spec."""
    activity = WithingsActivity.model_validate({"date": "2020-06-24", "brand": 18, "is_tracker": False, "steps": 8000})
    assert activity.brand == 18
    assert activity.is_tracker is False
    assert activity.deviceid is None
