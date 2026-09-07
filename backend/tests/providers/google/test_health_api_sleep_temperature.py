"""Google Health API: daily-sleep-temperature-derivations → skin_temperature (daily total).

Registry entry + list-path mapping. Payload field names follow the DataPoint reference
(users.dataTypes.dataPoints#dailysleeptemperaturederivations).
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import DataGranularity, SeriesType
from app.schemas.providers.google import TimeShape
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.health_api.metrics import METRICS

DATA_TYPE = "daily-sleep-temperature-derivations"
_BY_TYPE = {m.data_type: m for m in METRICS}


@pytest.mark.parametrize(
    ("data_type", "value_key", "field", "series_type"),
    [
        (DATA_TYPE, "dailySleepTemperatureDerivations", "nightlyTemperatureCelsius", SeriesType.skin_temperature),
        ("daily-resting-heart-rate", "dailyRestingHeartRate", "beatsPerMinute", SeriesType.resting_heart_rate),
    ],
)
def test_daily_metric_is_registered_as_list_only_daily_total(
    data_type: str, value_key: str, field: str, series_type: SeriesType
) -> None:
    metric = _BY_TYPE[data_type]
    assert metric.value_key == value_key
    assert metric.series_type == series_type
    assert metric.rollup_spec is None, "Daily types only support list/reconcile"
    assert metric.list_spec is not None
    assert metric.list_spec.field == field
    assert metric.list_spec.time is TimeShape.DATE
    assert metric.list_spec.is_daily_total is True
    for granularity in DataGranularity:
        assert metric.use_list(granularity)


def test_registry_has_no_duplicate_data_types() -> None:
    types = [m.data_type for m in METRICS]
    assert len(types) == len(set(types))


def _handler() -> GoogleHealth247Data:
    return GoogleHealth247Data(
        oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="https://health.googleapis.com"
    )


def test_native_samples_map_daily_point_to_one_daily_total_sample() -> None:
    handler = _handler()
    metric = _BY_TYPE[DATA_TYPE]
    user_id = uuid4()
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 8, tzinfo=timezone.utc)
    point = {
        "name": f"users/me/dataTypes/{DATA_TYPE}/dataPoints/abc",
        "dailySleepTemperatureDerivations": {
            "date": {"year": 2026, "month": 9, "day": 5},
            "nightlyTemperatureCelsius": 34.62,
            "baselineTemperatureCelsius": 34.8,
            "relativeNightlyStddev30dCelsius": 0.21,
        },
    }

    with patch.object(GoogleHealth247Data, "_fetch_points", return_value=[point]) as fetch:
        samples = handler._native_samples(MagicMock(), user_id, metric, start, end)

    endpoint = fetch.call_args.args[2]
    assert DATA_TYPE in endpoint
    time_filter = fetch.call_args.args[3]
    assert time_filter.startswith(f"{DATA_TYPE.replace('-', '_')}.date >= ")

    assert len(samples) == 1, "only the nightly temperature is a measurement; baseline/stddev are not emitted"
    sample = samples[0]
    assert sample.series_type == SeriesType.skin_temperature
    assert sample.value == Decimal("34.62")
    assert sample.is_daily_total is True
    assert sample.recorded_at == datetime(2026, 9, 5, tzinfo=timezone.utc)
    assert sample.zone_offset is None
    assert sample.user_id == user_id
    assert sample.provider == "google"


def test_native_samples_skip_points_outside_window_and_without_value() -> None:
    handler = _handler()
    metric = _BY_TYPE[DATA_TYPE]
    points = [
        {
            "dailySleepTemperatureDerivations": {
                "date": {"year": 2026, "month": 8, "day": 1},
                "nightlyTemperatureCelsius": 34.0,
            }
        },
        {"dailySleepTemperatureDerivations": {"date": {"year": 2026, "month": 9, "day": 5}}},
        {
            "dailySleepTemperatureDerivations": {
                "date": {"year": 2026, "month": 9, "day": 6},
                "nightlyTemperatureCelsius": 34.9,
            }
        },
    ]
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 8, tzinfo=timezone.utc)
    with patch.object(GoogleHealth247Data, "_fetch_points", return_value=points):
        samples = handler._native_samples(MagicMock(), uuid4(), metric, start, end)
    assert [s.value for s in samples] == [Decimal("34.9")]


def test_sync_data_type_routes_the_new_type() -> None:
    """Webhook pings for the new type reach the registry (sync_data_type returns None only for unknown types)."""
    handler = _handler()
    with (
        patch.object(GoogleHealth247Data, "_native_samples", return_value=[]) as native,
        patch.object(handler.settings_repo, "get_data_granularity", return_value=DataGranularity.RAW),
    ):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        end = datetime(2026, 9, 2, tzinfo=timezone.utc)
        assert handler.sync_data_type(MagicMock(), uuid4(), DATA_TYPE, start, end) is None
        assert native.call_count == 1
        assert handler.sync_data_type(MagicMock(), uuid4(), "not-a-type", start, end) is None
        assert native.call_count == 1
