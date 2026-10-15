"""Withings payload normalization for measures, activity, sleep and workouts."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.constants.withings_requests import ACTIVITY
from app.schemas.enums import SeriesType
from app.schemas.enums.workout_types import WorkoutType
from app.schemas.providers.withings import WithingsWorkout
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.handlers.rpc_client import WithingsAPIError
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
    assert by_type[SeriesType.active_energy].value == Decimal("400.0")
    assert by_type[SeriesType.basal_energy].value == Decimal("1800.0")
    assert by_type[SeriesType.steps].is_daily_total is True


def test_externally_sourced_activity_is_dropped() -> None:
    # brand 18 is Withings' code for a re-imported external source; counting it
    # would double the origin connector the user may have linked directly.
    rows = [{"date": "2026-03-01", "brand": 18, "steps": 8000}]

    assert _data_247().normalize_activity(rows, uuid4()) == []


def test_activity_active_seconds_become_exercise_minutes() -> None:
    rows = [{"date": "2026-03-01", "timezone": "Europe/Paris", "brand": 1, "steps": 8000, "active": 2730}]

    samples = _data_247().normalize_activity(rows, uuid4())

    by_type = {sample.series_type: sample for sample in samples}
    assert by_type[SeriesType.exercise_time].value == Decimal("45")
    assert by_type[SeriesType.exercise_time].is_daily_total is True


def test_activity_without_active_has_no_exercise_time() -> None:
    rows = [{"date": "2026-03-01", "brand": 1, "steps": 8000}]

    samples = _data_247().normalize_activity(rows, uuid4())

    assert SeriesType.exercise_time not in {sample.series_type for sample in samples}


def test_activity_request_asks_for_active() -> None:
    assert "active" in ACTIVITY.data_fields


# ---------------------------- intraday activity ----------------------------

INTRADAY_SLICE = {"model_id": 55, "steps": 120, "distance": 96.5, "calories": 7.5}


def test_intraday_slice_is_keyed_by_epoch_and_is_not_a_daily_total() -> None:
    samples = _data_247().normalize_intraday_activity({"1772346600": INTRADAY_SLICE}, uuid4())

    by_type = {sample.series_type: sample for sample in samples}
    assert by_type[SeriesType.steps].value == Decimal("120")
    assert by_type[SeriesType.steps].recorded_at == datetime(2026, 3, 1, 6, 30, tzinfo=timezone.utc)
    # The daily total covering this slice is stored too; flagging both the same way
    # would let the aggregation add a day to its own parts.
    assert by_type[SeriesType.steps].is_daily_total is False


def test_intraday_slice_from_a_relayed_tracker_is_dropped() -> None:
    # 1058 is an Apple Watch relayed through the Withings account; those steps
    # already reach us from the provider that recorded them.
    series = {"1772346600": {**INTRADAY_SLICE, "model_id": 1058}}

    assert _data_247().normalize_intraday_activity(series, uuid4()) == []


def test_intraday_slice_with_an_unreadable_epoch_is_skipped() -> None:
    series = {"not-an-epoch": INTRADAY_SLICE, "1772346600": INTRADAY_SLICE}

    samples = _data_247().normalize_intraday_activity(series, uuid4())

    assert {sample.recorded_at for sample in samples} == {datetime(2026, 3, 1, 6, 30, tzinfo=timezone.utc)}


def test_intraday_slice_takes_the_zone_reported_for_its_day() -> None:
    # An hour of the day is a local one, and the intraday response carries no zone.
    timezones = {date(2026, 3, 1): "Europe/Warsaw"}

    samples = _data_247().normalize_intraday_activity({"1772346600": INTRADAY_SLICE}, uuid4(), None, timezones)

    assert {sample.zone_offset for sample in samples} == {"+01:00"}


def test_intraday_slice_on_the_local_day_start_is_dropped() -> None:
    # save_activity stores the day's totals at local midnight, and the two are written in
    # separate batches, so a slice on that instant would upsert the totals away.
    timezones = {date(2026, 3, 1): "Europe/Warsaw"}
    local_midnight = str(int(datetime(2026, 2, 28, 23, tzinfo=timezone.utc).timestamp()))

    samples = _data_247().normalize_intraday_activity({local_midnight: INTRADAY_SLICE}, uuid4(), None, timezones)

    assert samples == []


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_is_requested_only_for_days_the_daily_rows_report(
    mock_intraday: MagicMock, mock_daily: MagicMock
) -> None:
    # The action returns at most 24 h per call, so a window costs one request per day.
    # Asking for days Withings never reported would spend the per-minute quota on nothing
    # and leave none for the domains that run after this one.
    mock_intraday.return_value = {}
    mock_daily.return_value = MagicMock(
        rows=[
            {"date": "2026-03-01", "timezone": "Europe/Warsaw", "brand": 1, "steps": 1},
            {"date": "2026-03-03", "timezone": "Europe/Warsaw", "brand": 1, "steps": 2},
        ]
    )
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    data_247.save_intraday_activity(
        MagicMock(),
        uuid4(),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 3, 5, tzinfo=timezone.utc),
    )

    # Local midnight in Warsaw, not the window's own edges: the day asked for is the user's.
    starts = [call.kwargs["params"]["startdate"] for call in mock_intraday.call_args_list]
    assert starts == [
        int(datetime(2026, 2, 28, 23, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 2, 23, tzinfo=timezone.utc).timestamp()),
    ]


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_asks_for_nothing_when_no_day_reported_activity(
    mock_intraday: MagicMock, mock_daily: MagicMock
) -> None:
    mock_daily.return_value = MagicMock(rows=[])
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    saved = data_247.save_intraday_activity(
        MagicMock(),
        uuid4(),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 4, 1, tzinfo=timezone.utc),
    )

    assert saved == 0
    assert mock_intraday.call_args_list == []


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_asks_for_a_day_without_a_zone(mock_intraday: MagicMock, mock_daily: MagicMock) -> None:
    # A missing zone costs the local offset, not the day: it is asked for from UTC midnight.
    mock_intraday.return_value = {}
    mock_daily.return_value = MagicMock(rows=[{"date": "2026-03-01", "brand": 1, "steps": 1}])
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    data_247.save_intraday_activity(
        MagicMock(), uuid4(), datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 2, tzinfo=timezone.utc)
    )

    starts = [call.kwargs["params"]["startdate"] for call in mock_intraday.call_args_list]
    assert starts == [int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())]


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_zone_ignores_externally_sourced_rows(mock_intraday: MagicMock, mock_daily: MagicMock) -> None:
    # The day's total comes from the Withings row only, so an echo row in another zone
    # must not move the midnight the intraday request and its guard are anchored to.
    mock_intraday.return_value = {}
    mock_daily.return_value = MagicMock(
        rows=[
            {"date": "2026-03-01", "timezone": "Europe/Warsaw", "brand": 1, "steps": 1},
            {"date": "2026-03-01", "timezone": "America/New_York", "brand": 18, "steps": 1},
        ]
    )
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    data_247.save_intraday_activity(
        MagicMock(), uuid4(), datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 2, tzinfo=timezone.utc)
    )

    starts = [call.kwargs["params"]["startdate"] for call in mock_intraday.call_args_list]
    assert starts == [int(datetime(2026, 2, 28, 23, tzinfo=timezone.utc).timestamp())]


TWO_DAYS = [
    {"date": "2026-03-01", "timezone": "Europe/Warsaw", "brand": 1, "steps": 1},
    {"date": "2026-03-02", "timezone": "Europe/Warsaw", "brand": 1, "steps": 1},
]


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_keeps_the_days_fetched_before_a_failure(
    mock_intraday: MagicMock, mock_daily: MagicMock, mock_timeseries: MagicMock
) -> None:
    mock_daily.return_value = MagicMock(rows=TWO_DAYS)
    mock_intraday.side_effect = [{"1772346600": INTRADAY_SLICE}, RuntimeError("Too Many Requests")]
    mock_timeseries.bulk_create_samples.return_value = 3
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    saved = data_247.save_intraday_activity(
        MagicMock(), uuid4(), datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 3, tzinfo=timezone.utc)
    )

    assert saved == 3
    written = mock_timeseries.bulk_create_samples.call_args.args[1]
    assert {sample.recorded_at for sample in written} == {datetime(2026, 3, 1, 6, 30, tzinfo=timezone.utc)}


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_intraday_failure_before_anything_is_fetched_propagates(
    mock_intraday: MagicMock, mock_daily: MagicMock
) -> None:
    mock_daily.return_value = MagicMock(rows=TWO_DAYS)
    mock_intraday.side_effect = RuntimeError("Too Many Requests")
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    with pytest.raises(RuntimeError):
        data_247.save_intraday_activity(
            MagicMock(), uuid4(), datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 3, tzinfo=timezone.utc)
        )


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


# ---------------------------- sleep ----------------------------

SLEEP_ROW = {
    "startdate": 1594159200,
    "enddate": 1594188000,
    "id": 12345,
    "timezone": "Europe/Warsaw",
    "data": {
        "total_timeinbed": 28800,
        "total_sleep_time": 25200,
        "deepsleepduration": 7200,
        "lightsleepduration": 14400,
        "remsleepduration": 3600,
        "wakeupduration": 3600,
        "sleep_efficiency": 0.875,
        "hr_min": 48,
    },
}
SERIES_BODY = {
    "series": [
        {"startdate": 1594159200, "enddate": 1594160100, "state": 1},
        {"startdate": 1594160100, "enddate": 1594163700, "state": 2},
        {"startdate": 1594163700, "enddate": 1594164600, "state": 0},
        {"startdate": 1594164600, "enddate": 1594167300, "state": 5},
        {"startdate": 1594167300, "enddate": 1594168200, "state": 15},
    ]
}


_WINDOW = (datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 7, 8, tzinfo=timezone.utc))


def _save_one_night(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = MagicMock(rows=[SLEEP_ROW])
    _data_247().save_sleep(MagicMock(), uuid4(), *_WINDOW)


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", side_effect=[SERIES_BODY, {"series": []}])
@patch("app.services.providers.withings.data_247.paginate")
def test_sleep_row_stores_the_hypnogram(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    _save_one_night(mock_paginate)

    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert [stage.stage.value for stage in detail.sleep_stages] == ["light", "deep", "awake", "sleeping", "awake"]
    assert mock_request.call_args.kwargs["service_path"] == "/v2/sleep"
    assert mock_request.call_args.kwargs["action"] == "get"


HRV_SERIES_BODY = {
    "series": [
        {
            "startdate": 1594159200,
            "enddate": 1594160100,
            "state": 1,
            "rmssd": {"1594159200": 25, "1594159260": 0, "1594159320": None},
        },
        # Unmapped state, but its readings still count.
        {"startdate": 1594160100, "enddate": 1594163700, "state": 99, "sdnn_1": {"1594160100": 30}},
        # After the night ends, so no night claims it.
        {"startdate": 1594188000, "enddate": 1594188600, "state": 0, "rmssd": {"1594188300": 40}},
    ]
}


def _saved_hrv(mock_timeseries: MagicMock) -> dict[SeriesType, list[float]]:
    samples = mock_timeseries.bulk_create_samples.call_args.args[1]
    hrv: dict[SeriesType, list[float]] = {}
    for sample in samples:
        if sample.series_type in (SeriesType.heart_rate_variability_rmssd, SeriesType.heart_rate_variability_sdnn):
            hrv.setdefault(sample.series_type, []).append(float(sample.value))
    return hrv


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", side_effect=[HRV_SERIES_BODY, {"series": []}])
@patch("app.services.providers.withings.data_247.paginate")
def test_sleep_hrv_readings_become_samples_of_their_night(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    _save_one_night(mock_paginate)

    assert mock_request.call_args.kwargs["params"]["data_fields"] == "rmssd,sdnn_1"
    # 0 and null are missed readings; their interval keeps its stage.
    assert _saved_hrv(mock_timeseries) == {
        SeriesType.heart_rate_variability_rmssd: [25.0],
        SeriesType.heart_rate_variability_sdnn: [30.0],
    }
    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert detail.sleep_stages[0].stage.value == "light"


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch(
    "app.services.providers.withings.data_247.withings_request",
    side_effect=[WithingsAPIError(withings_status=2555, action="get"), SERIES_BODY, {"series": []}],
)
@patch("app.services.providers.withings.data_247.paginate")
def test_hypnogram_survives_the_hrv_fields_being_refused(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    # A plan without the HRV pack must still get its stages.
    _save_one_night(mock_paginate)

    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert [stage.stage.value for stage in detail.sleep_stages] == ["light", "deep", "awake", "sleeping", "awake"]
    assert "data_fields" not in mock_request.call_args_list[1].kwargs["params"]


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch(
    "app.services.providers.withings.data_247.withings_request",
    side_effect=WithingsAPIError(withings_status=601, action="get"),
)
@patch("app.services.providers.withings.data_247.paginate")
def test_throttled_hypnogram_is_not_asked_again_without_the_hrv_fields(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    # withings_request has already backed off; asking again would wait out the quota twice.
    _save_one_night(mock_paginate)

    assert mock_request.call_count == 1


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", side_effect=[HRV_SERIES_BODY, {"series": []}])
@patch("app.services.providers.withings.data_247.paginate")
def test_sleep_hrv_is_kept_for_a_night_without_a_lowest_heart_rate(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    mock_paginate.return_value = MagicMock(rows=[{**SLEEP_ROW, "data": {**SLEEP_ROW["data"], "hr_min": None}}])

    _data_247().save_sleep(MagicMock(), uuid4(), *_WINDOW)

    assert SeriesType.heart_rate_variability_rmssd in _saved_hrv(mock_timeseries)


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", side_effect=RuntimeError("boom"))
@patch("app.services.providers.withings.data_247.paginate")
def test_night_is_saved_when_the_hypnogram_call_fails(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    _save_one_night(mock_paginate)

    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert detail.sleep_stages is None
    assert detail.sleep_deep_minutes == 120


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request")
@patch("app.services.providers.withings.data_247.paginate")
def test_two_nights_share_one_hypnogram_request(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    second_night = {**SLEEP_ROW, "id": 12346, "startdate": 1594245600, "enddate": 1594274400}
    mock_paginate.return_value = MagicMock(rows=[SLEEP_ROW, second_night])
    mock_request.side_effect = [
        {
            "series": [
                {"startdate": 1594160100, "enddate": 1594163700, "state": 2},
                {"startdate": 1594246500, "enddate": 1594250100, "state": 1},
            ]
        },
        {"series": []},
    ]

    saved = _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 7, 9, tzinfo=timezone.utc)
    )

    assert saved == 2
    # The window is walked until a page adds nothing, never once per night.
    assert mock_request.call_count == 2
    first_call = mock_request.call_args_list[0].kwargs["params"]
    assert first_call["startdate"] <= SLEEP_ROW["startdate"]
    assert first_call["enddate"] >= second_night["enddate"]
    first, second = (call.args[3] for call in mock_event.create_or_merge_sleep.call_args_list)
    assert [stage.stage.value for stage in first.sleep_stages] == ["deep"]
    assert [stage.stage.value for stage in second.sleep_stages] == ["light"]


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request")
@patch("app.services.providers.withings.data_247.paginate")
def test_a_gap_longer_than_a_page_does_not_cut_the_walk_short(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    ten_days = 10 * 86400
    later_night = {
        **SLEEP_ROW,
        "id": 12347,
        "startdate": SLEEP_ROW["startdate"] + ten_days,
        "enddate": SLEEP_ROW["enddate"] + ten_days,
    }
    mock_paginate.return_value = MagicMock(rows=[SLEEP_ROW, later_night])
    mock_request.side_effect = [
        {"series": [{"startdate": 1594160100, "enddate": 1594163700, "state": 2}]},
        # Nothing for the stretch after the first night, the way Withings answers an empty range.
        {"series": []},
        {"series": [{"startdate": later_night["startdate"], "enddate": later_night["startdate"] + 3600, "state": 1}]},
        {"series": []},
    ]

    _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 7, 20, tzinfo=timezone.utc)
    )

    first, second = (call.args[3] for call in mock_event.create_or_merge_sleep.call_args_list)
    assert [stage.stage.value for stage in first.sleep_stages] == ["deep"]
    assert [stage.stage.value for stage in second.sleep_stages] == ["light"]


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.log_and_capture_error")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request")
@patch("app.services.providers.withings.data_247.paginate")
def test_every_night_gets_stages_when_a_page_reaches_only_one_night(
    mock_paginate: MagicMock,
    mock_request: MagicMock,
    mock_event: MagicMock,
    mock_error: MagicMock,
    mock_timeseries: MagicMock,
) -> None:
    # Withings documents a 24h cap on this endpoint, which makes a long sync one page per night.
    nights = [
        {
            **SLEEP_ROW,
            "id": 100 + day,
            "startdate": SLEEP_ROW["startdate"] + day * 86400,
            "enddate": SLEEP_ROW["enddate"] + day * 86400,
        }
        for day in range(70)
    ]
    mock_paginate.return_value = MagicMock(rows=nights)
    mock_request.side_effect = [
        {"series": [{"startdate": night["startdate"] + 900, "enddate": night["startdate"] + 4500, "state": 2}]}
        for night in nights
    ] + [{"series": []}]

    _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 9, 20, tzinfo=timezone.utc)
    )

    stored = [call.args[3].sleep_stages for call in mock_event.create_or_merge_sleep.call_args_list]
    assert len(stored) == len(nights)
    assert all(stages for stages in stored), "a night was saved without stages"
    # The walk ends because it covered the nights, not because a request blew up.
    mock_error.assert_not_called()


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.log_structured")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request")
@patch("app.services.providers.withings.data_247.paginate")
def test_a_walk_that_runs_out_of_requests_says_so(
    mock_paginate: MagicMock,
    mock_request: MagicMock,
    mock_event: MagicMock,
    mock_log: MagicMock,
    mock_timeseries: MagicMock,
) -> None:
    # A page that creeps forward a minute at a time never reaches the end of the night.
    def one_minute(**kwargs: dict) -> dict:
        start = kwargs["params"]["startdate"]
        return {"series": [{"startdate": start, "enddate": start + 60, "state": 1}]}

    mock_paginate.return_value = MagicMock(rows=[SLEEP_ROW])
    mock_request.side_effect = one_minute

    _data_247().save_sleep(MagicMock(), uuid4(), *_WINDOW)

    levels = [call.args[1] for call in mock_log.call_args_list]
    assert "warning" in levels


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_minute_by_minute_states_are_folded_into_one_interval(
    mock_paginate: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    minute_states = {
        "series": [
            {"startdate": 1594159200 + 60 * i, "enddate": 1594159200 + 60 * (i + 1), "state": 0} for i in range(8)
        ]
        + [{"startdate": 1594159680, "enddate": 1594163700, "state": 1}]
    }
    with patch(
        "app.services.providers.withings.data_247.withings_request",
        side_effect=[minute_states, {"series": []}],
    ):
        _save_one_night(mock_paginate)

    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert [stage.stage.value for stage in detail.sleep_stages] == ["awake", "light"]
    assert detail.sleep_stages[0].end_time == detail.sleep_stages[1].start_time


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", side_effect=[SERIES_BODY, {"series": []}])
@patch("app.services.providers.withings.data_247.paginate")
def test_a_night_with_unreadable_timestamps_does_not_drop_the_batch(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    mock_paginate.return_value = MagicMock(
        rows=[
            {**SLEEP_ROW, "id": 1, "startdate": "broken"},
            # A number Withings could never mean: past the range datetime can represent.
            {**SLEEP_ROW, "id": 2, "startdate": 10**13},
            SLEEP_ROW,
        ]
    )

    assert _data_247().save_sleep(MagicMock(), uuid4(), *_WINDOW) == 1


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_a_stage_running_past_the_night_is_clipped(
    mock_paginate: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    # Last state starts inside the night and runs an hour past its end.
    overrunning = {"series": [{"startdate": 1594187700, "enddate": 1594191600, "state": 1}]}
    with patch("app.services.providers.withings.data_247.withings_request", side_effect=[overrunning, {"series": []}]):
        _save_one_night(mock_paginate)

    detail = mock_event.create_or_merge_sleep.call_args.args[3]
    assert detail.sleep_stages[0].end_time == datetime.fromtimestamp(SLEEP_ROW["enddate"], tz=timezone.utc)


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", return_value={"series": []})
@patch("app.services.providers.withings.data_247.paginate")
def test_the_night_low_heart_rate_becomes_a_resting_heart_rate_sample(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    mock_paginate.return_value = MagicMock(rows=[SLEEP_ROW])

    _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 7, 8, tzinfo=timezone.utc)
    )

    samples = mock_timeseries.bulk_create_samples.call_args.args[1]
    rhr = next(sample for sample in samples if sample.series_type == SeriesType.resting_heart_rate)
    assert float(rhr.value) == 48
    assert rhr.recorded_at == datetime.fromtimestamp(SLEEP_ROW["startdate"], tz=timezone.utc)
    assert rhr.zone_offset == "+02:00"


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", return_value={"series": []})
@patch("app.services.providers.withings.data_247.paginate")
def test_the_sample_carries_the_offset_in_force_when_the_night_began(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    # Warsaw goes from +02:00 to +01:00 at 03:00 local on 2020-10-25, mid-night.
    dst_night = {
        **SLEEP_ROW,
        "startdate": int(datetime(2020, 10, 24, 21, tzinfo=timezone.utc).timestamp()),
        "enddate": int(datetime(2020, 10, 25, 6, tzinfo=timezone.utc).timestamp()),
    }
    mock_paginate.return_value = MagicMock(rows=[dst_night])

    _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 10, 24, tzinfo=timezone.utc), datetime(2020, 10, 26, tzinfo=timezone.utc)
    )

    sample = mock_timeseries.bulk_create_samples.call_args.args[1][0]
    assert sample.zone_offset == "+02:00"


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.withings_request", return_value={"series": []})
@patch("app.services.providers.withings.data_247.paginate")
def test_a_night_without_a_low_heart_rate_is_still_saved(
    mock_paginate: MagicMock, mock_request: MagicMock, mock_event: MagicMock, mock_timeseries: MagicMock
) -> None:
    without_hr = {**SLEEP_ROW, "data": {k: v for k, v in SLEEP_ROW["data"].items() if k != "hr_min"}}
    mock_paginate.return_value = MagicMock(rows=[without_hr])

    saved = _data_247().save_sleep(
        MagicMock(), uuid4(), datetime(2020, 7, 7, tzinfo=timezone.utc), datetime(2020, 7, 8, tzinfo=timezone.utc)
    )

    assert saved == 1
    mock_timeseries.bulk_create_samples.assert_not_called()


@patch("app.services.providers.withings.data_247.paginate")
@patch("app.services.providers.withings.data_247.paginate_mapping")
def test_one_sync_asks_for_the_daily_rows_once(mock_intraday: MagicMock, mock_paginate: MagicMock) -> None:
    # Daily and intraday activity both start from getactivity; a second call only spends quota.
    mock_intraday.return_value = {}
    mock_paginate.return_value = MagicMock(rows=TWO_DAYS)
    data_247 = _data_247()
    data_247._active_connection_id = MagicMock(return_value=None)

    with patch.object(data_247, "save_measures", return_value=0), patch.object(data_247, "save_sleep", return_value=0):
        data_247.load_and_save_all(
            MagicMock(), uuid4(), datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 3, tzinfo=timezone.utc)
        )

    actions = [call.kwargs["action"] for call in mock_paginate.call_args_list]
    assert actions.count("getactivity") == 1
    assert mock_intraday.call_count == 2
