"""Civil-day totals read straight from one dailyRollUp data type.

active-minutes reports whole minutes per activity level; exercise_time keeps the
moderate and vigorous ones, unweighted. Days without active-minutes fall back to
active-zone-minutes, unweighted the same way.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.metrics import DAILY_ROLLUP_METRICS

USER_ID = uuid4()
END = datetime(2026, 9, 3, tzinfo=timezone.utc)
START = END - timedelta(days=2)

ACTIVE_MINUTES = next(m for m in DAILY_ROLLUP_METRICS if m.series_type is SeriesType.exercise_time)


@pytest.fixture
def data_247() -> GoogleHealth247Data:
    return GoogleHealth247Data(
        oauth=MagicMock(),
        connection_repo=MagicMock(),
        api_base_url="https://health.googleapis.com",
    )


def _point(day: int, levels: dict[str, str] | None) -> dict:
    value = (
        {}
        if levels is None
        else {
            "activeMinutesRollupByActivityLevel": [
                {"activityLevel": level, "activeMinutesSum": minutes} for level, minutes in levels.items()
            ]
        }
    )
    return {"civilStartTime": {"date": {"year": 2026, "month": 9, "day": day}}, "activeMinutes": value}


def _samples(data_247: GoogleHealth247Data, points: list[dict]) -> list:
    with patch.object(data_247, "_fetch_rollup_pages", return_value=points):
        return data_247._daily_rollup_samples(MagicMock(), USER_ID, ACTIVE_MINUTES, START, END)


def test_sums_moderate_and_vigorous_minutes(data_247: GoogleHealth247Data) -> None:
    samples = _samples(data_247, [_point(1, {"LIGHT": "95", "MODERATE": "12", "VIGOROUS": "8"})])

    assert [(s.recorded_at, s.value) for s in samples] == [(datetime(2026, 9, 1, tzinfo=timezone.utc), Decimal(20))]
    assert samples[0].series_type is SeriesType.exercise_time
    assert samples[0].is_daily_total is True


def test_a_day_with_only_light_activity_is_zero(data_247: GoogleHealth247Data) -> None:
    samples = _samples(data_247, [_point(1, {"LIGHT": "95"})])

    assert [s.value for s in samples] == [Decimal(0)]


def test_a_day_without_the_level_list_has_no_sample(data_247: GoogleHealth247Data) -> None:
    assert _samples(data_247, [_point(1, None)]) == []


def test_an_omitted_sum_counts_as_zero(data_247: GoogleHealth247Data) -> None:
    # Google omits zero int64 fields from its JSON.
    point = {
        "civilStartTime": {"date": {"year": 2026, "month": 9, "day": 1}},
        "activeMinutes": {
            "activeMinutesRollupByActivityLevel": [
                {"activityLevel": "MODERATE"},
                {"activityLevel": "VIGOROUS", "activeMinutesSum": "7"},
            ]
        },
    }

    assert [s.value for s in _samples(data_247, [point])] == [Decimal(7)]


def _zone_point(day: int, zones: dict[str, str]) -> dict:
    return {"civilStartTime": {"date": {"year": 2026, "month": 9, "day": day}}, "activeZoneMinutes": zones}


def _samples_by_type(data_247: GoogleHealth247Data, points: dict[str, list[dict]]) -> list:
    def fetch(db: object, user_id: object, endpoint: str, body: object) -> list[dict]:
        return points.get(endpoint.split("/")[5], [])

    with patch.object(data_247, "_fetch_rollup_pages", side_effect=fetch):
        return data_247._daily_rollup_samples(MagicMock(), USER_ID, ACTIVE_MINUTES, START, END)


def test_zone_minutes_are_unweighted_when_active_minutes_are_missing(data_247: GoogleHealth247Data) -> None:
    # 10 fat-burn minutes (weight 1) + 6 cardio and 2 peak minutes (weight 2).
    zones = {"sumInFatBurnHeartZone": "10", "sumInCardioHeartZone": "12", "sumInPeakHeartZone": "4"}

    samples = _samples_by_type(data_247, {"active-zone-minutes": [_zone_point(1, zones)]})

    assert [(s.recorded_at, s.value) for s in samples] == [(datetime(2026, 9, 1, tzinfo=timezone.utc), Decimal(18))]
    assert samples[0].series_type is SeriesType.exercise_time


def test_an_omitted_zone_counts_as_zero(data_247: GoogleHealth247Data) -> None:
    samples = _samples_by_type(data_247, {"active-zone-minutes": [_zone_point(1, {"sumInCardioHeartZone": "8"})]})

    assert [s.value for s in samples] == [Decimal(4)]


def test_active_minutes_win_over_zone_minutes_on_the_same_day(data_247: GoogleHealth247Data) -> None:
    samples = _samples_by_type(
        data_247,
        {
            "active-minutes": [_point(1, {"MODERATE": "12", "VIGOROUS": "8"})],
            "active-zone-minutes": [
                _zone_point(1, {"sumInFatBurnHeartZone": "30"}),
                _zone_point(2, {"sumInFatBurnHeartZone": "5"}),
            ],
        },
    )

    assert [(s.recorded_at.day, s.value) for s in samples] == [(1, Decimal(20)), (2, Decimal(5))]


def test_active_minutes_requests_at_most_14_days_at_a_time(data_247: GoogleHealth247Data) -> None:
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    start = end - timedelta(days=30)

    with patch.object(data_247, "_fetch_rollup_pages", return_value=[]) as fetch:
        data_247._daily_rollup_samples(MagicMock(), USER_ID, ACTIVE_MINUTES, start, end)

    assert fetch.call_count > 1
    for call in fetch.call_args_list:
        assert call.args[2] in {
            "/v4/users/me/dataTypes/active-minutes/dataPoints:dailyRollUp",
            "/v4/users/me/dataTypes/active-zone-minutes/dataPoints:dailyRollUp",
        }
        window = call.args[3]["range"]
        first, last = (date(**window[key]["date"]) for key in ("start", "end"))
        assert (last - first).days <= 14


def test_a_full_sync_fetches_active_minutes_through_daily_rollup(data_247: GoogleHealth247Data) -> None:
    calls: list[str] = []

    def fake_request(*args: object, **kwargs: object) -> object:
        calls.append(str(kwargs.get("endpoint")))
        return {}

    with (
        patch(
            "app.services.providers.google_health.data_247.make_authenticated_request",
            side_effect=fake_request,
        ),
        patch.object(data_247.sleep, "load_and_save", return_value=0),
        patch.object(data_247.settings_repo, "get_data_granularity", return_value=None),
        patch("app.services.providers.google_health.data_247.store_raw_payload"),
    ):
        data_247.load_and_save_all(MagicMock(), USER_ID, START, END)

    assert "/v4/users/me/dataTypes/active-minutes/dataPoints:dailyRollUp" in calls
    assert "/v4/users/me/dataTypes/active-zone-minutes/dataPoints:dailyRollUp" in calls
