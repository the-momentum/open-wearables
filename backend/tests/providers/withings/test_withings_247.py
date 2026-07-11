from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.config import settings
from app.schemas.enums import SeriesType
from app.services.providers.withings.coverage import MEASURE_TYPE_MAP
from app.services.providers.withings.data_247 import Withings247Data


def _make_data_247() -> Withings247Data:
    return Withings247Data(provider_name="withings", api_base_url="https://wbsapi.withings.net", oauth=MagicMock())


def test_normalize_measures_maps_types_and_scales() -> None:
    d = _make_data_247()
    user_id = uuid4()
    groups = [
        {
            "date": 1728000000,
            "measures": [
                {"value": 7500, "type": 1, "unit": -2},  # weight 75.00 kg
                {"value": 120, "type": 10, "unit": 0},  # systolic 120
                {"value": 80, "type": 9, "unit": 0},  # diastolic 80
                {"value": 98, "type": 119, "unit": 0},  # glucose 98 mg/dL
                {"value": 45, "type": 155, "unit": 0},  # vascular age 45 years
            ],
        },
    ]
    samples = d.normalize_measures(groups, user_id)
    by_type = {s.series_type: s for s in samples}
    assert by_type[SeriesType.weight].value == Decimal("75.00")
    assert by_type[SeriesType.weight].source == "withings"
    assert by_type[SeriesType.blood_pressure_systolic].value == Decimal("120")
    assert by_type[SeriesType.blood_pressure_diastolic].value == Decimal("80")
    assert by_type[SeriesType.blood_glucose].value == Decimal("98")
    assert by_type[SeriesType.cardiovascular_age].value == Decimal("45")
    expected_ts = datetime.fromtimestamp(1728000000, tz=timezone.utc)
    assert by_type[SeriesType.weight].recorded_at == expected_ts


def test_normalize_measures_drops_deferred_official_types() -> None:
    # These Withings types are either semantically mismatched with existing core
    # series or need new core concepts.
    d = _make_data_247()
    groups = [
        {
            "date": 1728000000,
            "measures": [
                {"value": 1500, "type": 88, "unit": -2},  # bone mass
                {"value": 1000, "type": 91, "unit": -2},  # pulse wave velocity
                {"value": 42000, "type": 77, "unit": -3},  # total body water
                {"value": 1, "type": 130, "unit": 0},  # AFib classification
                {"value": 12, "type": 196, "unit": 0},  # feet-specific EDA
                {"value": 1800, "type": 226, "unit": 0},  # BMR rate
                {"value": 40, "type": 227, "unit": 0},  # metabolic age
                {"value": 7500, "type": 1, "unit": -2},  # weight 75.00 kg → kept
            ],
        },
    ]
    samples = d.normalize_measures(groups, uuid4())
    assert {s.series_type for s in samples} == {SeriesType.weight}


def test_normalize_measures_converts_height_metres_to_cm() -> None:
    # Withings height (meastype 4) is metres; OW `height` series is centimetres.
    d = _make_data_247()
    groups = [{"date": 1728000000, "measures": [{"value": 180, "type": 4, "unit": -2}]}]  # 1.80 m
    by_type = {s.series_type: s for s in d.normalize_measures(groups, uuid4())}
    assert by_type[SeriesType.height].value == Decimal("180.00")


@patch("app.services.providers.withings.data_247.timeseries_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_save_measures_persists_samples(mock_paginate: MagicMock, mock_ts: MagicMock) -> None:
    d = _make_data_247()
    db = MagicMock()
    mock_paginate.return_value = [{"date": 1728000000, "measures": [{"value": 7500, "type": 1, "unit": -2}]}]
    count = d.save_measures(db, uuid4(), datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert count == 1
    assert mock_paginate.call_args.kwargs["service_path"] == "/measure"
    assert mock_paginate.call_args.kwargs["action"] == "getmeas"
    assert mock_paginate.call_args.kwargs["list_key"] == "measuregrps"
    requested = {int(code) for code in mock_paginate.call_args.kwargs["params"]["meastypes"].split(",")}
    assert requested == set(MEASURE_TYPE_MAP)
    mock_ts.bulk_create_samples.assert_called_once()


def test_normalize_activity_maps_metrics() -> None:
    d = _make_data_247()
    rows = [{"date": "2024-01-15", "steps": 8000, "distance": 6000.0, "calories": 350.0, "deviceid": "abc123"}]
    samples = d.normalize_activity(rows, uuid4())
    by_type = {s.series_type: s for s in samples}
    assert by_type[SeriesType.steps].value == Decimal("8000")
    assert by_type[SeriesType.distance_walking_running].value == Decimal("6000.0")
    assert by_type[SeriesType.energy].value == Decimal("350.0")
    assert by_type[SeriesType.steps].recorded_at == datetime(2024, 1, 15, tzinfo=timezone.utc)


def test_normalize_activity_skips_rows_without_deviceid() -> None:
    """Rows with no ``deviceid`` are foreign-aggregated echoes (e.g. via Health
    Connect) and are skipped; only Withings-hardware days are kept."""
    d = _make_data_247()
    rows = [
        {"date": "2024-01-15", "steps": 8000, "deviceid": None, "model": "Google Health Connect"},
        {"date": "2024-01-16", "steps": 9000},  # deviceid absent → echo
        {"date": "2024-01-17", "steps": 7000, "deviceid": "abc123"},  # genuine Withings hardware
    ]
    samples = d.normalize_activity(rows, uuid4())
    days = {s.recorded_at.date() for s in samples}
    assert days == {datetime(2024, 1, 17).date()}
    assert all(s.series_type == SeriesType.steps for s in samples)


@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_save_sleep_creates_event_record(mock_paginate: MagicMock, mock_event: MagicMock) -> None:
    d = _make_data_247()
    db = MagicMock()
    # start 22:00, end 06:00 next day → 8h in bed
    start = int(datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 16, 6, 0, tzinfo=timezone.utc).timestamp())
    mock_paginate.return_value = [
        {
            "id": 42,
            "startdate": start,
            "enddate": end,
            "data": {
                "deepsleepduration": 7200,
                "lightsleepduration": 14400,
                "remsleepduration": 5400,
                "wakeupduration": 1800,
                "sleep_efficiency": 0.9,
            },
        }
    ]
    count = d.save_sleep(
        db, uuid4(), datetime(2024, 1, 15, tzinfo=timezone.utc), datetime(2024, 1, 16, tzinfo=timezone.utc)
    )
    assert count == 1
    mock_event.create_or_merge_sleep.assert_called_once()
    call = mock_event.create_or_merge_sleep.call_args
    record = call.args[2]
    detail = call.args[3]
    threshold = call.args[4]
    assert record.category == "sleep"
    assert record.source == "withings"
    # 0–1 ratio stored on the 0–100 scale
    assert detail.sleep_efficiency_score == Decimal("90.0")
    assert threshold == settings.sleep_end_gap_minutes


@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_save_sleep_continues_on_row_error(mock_paginate: MagicMock, mock_event: MagicMock) -> None:
    d = _make_data_247()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 16, 6, 0, tzinfo=timezone.utc).timestamp())
    row = {
        "id": 1,
        "startdate": start,
        "enddate": end,
        "data": {
            "deepsleepduration": 7200,
            "lightsleepduration": 14400,
            "remsleepduration": 5400,
            "wakeupduration": 1800,
            "sleep_efficiency": 0.85,
        },
    }
    # Two identical rows; first call raises, second succeeds
    mock_paginate.return_value = [row, {**row, "id": 2}]
    mock_event.create_or_merge_sleep.side_effect = [Exception("boom"), None]

    count = d.save_sleep(
        db, uuid4(), datetime(2024, 1, 15, tzinfo=timezone.utc), datetime(2024, 1, 16, tzinfo=timezone.utc)
    )
    assert count == 1
    db.rollback.assert_called()


def test_load_and_save_all_calls_each_domain() -> None:
    d = _make_data_247()
    db = MagicMock()
    d.save_measures = MagicMock(return_value=3)
    d.save_activity = MagicMock(return_value=2)
    d.save_sleep = MagicMock(return_value=1)
    result = d.load_and_save_all(
        db, uuid4(), datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 8, tzinfo=timezone.utc)
    )
    assert result == {"measures": 3, "activity": 2, "sleep": 1}


def test_load_and_save_all_isolates_domain_errors() -> None:
    d = _make_data_247()
    db = MagicMock()
    d.save_measures = MagicMock(side_effect=Exception("boom"))
    d.save_activity = MagicMock(return_value=2)
    d.save_sleep = MagicMock(return_value=1)
    result = d.load_and_save_all(
        db, uuid4(), datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 8, tzinfo=timezone.utc)
    )
    assert result == {"measures": 0, "activity": 2, "sleep": 1}
    db.rollback.assert_called()


def test_normalize_measures_skips_malformed_group() -> None:
    """One unparseable measure group must not drop the whole getmeas batch."""
    d = _make_data_247()
    groups = [
        {"measures": [{"value": 1, "type": 1, "unit": 0}]},  # no "date" → unparseable
        {"date": 1728000000, "measures": [{"type": 1, "unit": 0}]},  # measure missing "value"
        {"date": 1728000000, "measures": [{"value": 7500, "type": 1, "unit": -2}]},  # valid
    ]
    samples = d.normalize_measures(groups, uuid4())
    assert len(samples) == 1
    assert samples[0].value == Decimal("75.00")


@patch("app.services.providers.withings.data_247.paginate")
def test_save_activity_uses_exact_ymd_window_by_default(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    d = Withings247Data(provider_name="withings", api_base_url="https://x", oauth=MagicMock())
    start = datetime(2018, 7, 2, tzinfo=timezone.utc)
    end = datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc)
    d.save_activity(MagicMock(), uuid4(), start, end)
    params = mock_paginate.call_args.kwargs["params"]
    assert mock_paginate.call_args.kwargs["service_path"] == "/v2/measure"
    assert mock_paginate.call_args.kwargs["action"] == "getactivity"
    assert mock_paginate.call_args.kwargs["list_key"] == "activities"
    assert params["data_fields"] == (
        "steps,distance,elevation,calories,totalcalories,soft,moderate,intense,hr_average,hr_min,hr_max"
    )
    assert params["startdateymd"] == "2018-07-02"
    assert params["enddateymd"] == "2018-07-02"


@patch("app.services.providers.withings.data_247.paginate")
def test_save_activity_can_widen_ymd_window_for_webhook_notify(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    d = Withings247Data(provider_name="withings", api_base_url="https://x", oauth=MagicMock())
    start = datetime(2018, 7, 2, tzinfo=timezone.utc)
    end = datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc)
    d.save_activity(MagicMock(), uuid4(), start, end, widen_ymd_window=True)
    params = mock_paginate.call_args.kwargs["params"]
    assert params["startdateymd"] == "2018-07-01"
    assert params["enddateymd"] == "2018-07-03"


@patch("app.services.providers.withings.data_247.paginate")
def test_save_sleep_uses_exact_ymd_window_by_default(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    d = Withings247Data(provider_name="withings", api_base_url="https://x", oauth=MagicMock())
    start = datetime(2018, 7, 2, tzinfo=timezone.utc)
    end = datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc)
    d.save_sleep(MagicMock(), uuid4(), start, end)
    params = mock_paginate.call_args.kwargs["params"]
    assert mock_paginate.call_args.kwargs["service_path"] == "/v2/sleep"
    assert mock_paginate.call_args.kwargs["action"] == "getsummary"
    assert mock_paginate.call_args.kwargs["list_key"] == "series"
    assert params["data_fields"] == (
        "deepsleepduration,lightsleepduration,remsleepduration,wakeupduration,"
        "sleep_efficiency,sleep_score,hr_average,rr_average"
    )
    assert params["startdateymd"] == "2018-07-02"
    assert params["enddateymd"] == "2018-07-02"


@patch("app.services.providers.withings.data_247.paginate")
def test_save_sleep_can_widen_ymd_window_for_webhook_notify(mock_paginate: MagicMock) -> None:
    mock_paginate.return_value = []
    d = Withings247Data(provider_name="withings", api_base_url="https://x", oauth=MagicMock())
    start = datetime(2018, 7, 2, tzinfo=timezone.utc)
    end = datetime(2018, 7, 2, 23, 0, tzinfo=timezone.utc)
    d.save_sleep(MagicMock(), uuid4(), start, end, widen_ymd_window=True)
    params = mock_paginate.call_args.kwargs["params"]
    assert params["startdateymd"] == "2018-07-01"
    assert params["enddateymd"] == "2018-07-03"


@patch("app.services.providers.withings.data_247.event_record_service")
@patch("app.services.providers.withings.data_247.paginate")
def test_save_sleep_skips_unparseable_row(mock_paginate: MagicMock, mock_event: MagicMock) -> None:
    """A getsummary row without startdate must not abort the rest of the batch."""
    d = _make_data_247()
    db = MagicMock()
    start = int(datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2024, 1, 16, 6, 0, tzinfo=timezone.utc).timestamp())
    valid = {"id": 1, "startdate": start, "enddate": end, "data": {"deepsleepduration": 7200}}
    malformed = {"id": 2, "enddate": end, "data": {}}  # no startdate → unparseable
    mock_paginate.return_value = [malformed, valid]

    count = d.save_sleep(
        db, uuid4(), datetime(2024, 1, 15, tzinfo=timezone.utc), datetime(2024, 1, 16, tzinfo=timezone.utc)
    )

    assert count == 1
    mock_event.create_or_merge_sleep.assert_called_once()
