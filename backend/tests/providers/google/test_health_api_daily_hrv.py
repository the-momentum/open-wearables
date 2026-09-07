"""Google Health API: daily-heart-rate-variability → heart_rate_variability_rmssd (daily total).

Registry entry + list-path mapping. Payload field names follow the DataPoint reference
(users.dataTypes.dataPoints#dailyheartratevariability).
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.enums import DataGranularity, SeriesType
from app.schemas.providers.google import TimeShape
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.health_api.metrics import METRICS

DATA_TYPE = "daily-heart-rate-variability"
_BY_TYPE = {m.data_type: m for m in METRICS}


def test_daily_hrv_is_registered_as_list_only_daily_total() -> None:
    metric = _BY_TYPE[DATA_TYPE]
    assert metric.value_key == "dailyHeartRateVariability"
    assert metric.series_type == SeriesType.heart_rate_variability_rmssd
    assert metric.rollup_spec is None, "Daily types only support list/reconcile"
    assert metric.list_spec is not None
    assert metric.list_spec.field == "averageHeartRateVariabilityMilliseconds"
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
        "name": f"users/me/dataTypes/{DATA_TYPE}/dataPoints/def",
        "dailyHeartRateVariability": {
            "date": {"year": 2026, "month": 9, "day": 5},
            "averageHeartRateVariabilityMilliseconds": 41.3,
            "nonRemHeartRateBeatsPerMinute": "52",
            "entropy": 2.7,
            "deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds": 45.1,
        },
    }

    with patch.object(GoogleHealth247Data, "_fetch_points", return_value=[point]) as fetch:
        samples = handler._native_samples(MagicMock(), user_id, metric, start, end)

    endpoint = fetch.call_args.args[2]
    assert DATA_TYPE in endpoint
    time_filter = fetch.call_args.args[3]
    assert time_filter.startswith(f"{DATA_TYPE.replace('-', '_')}.date >= ")

    assert len(samples) == 1, "only the RMSSD average is emitted; deep-sleep RMSSD, non-REM HR and entropy are not"
    sample = samples[0]
    assert sample.series_type == SeriesType.heart_rate_variability_rmssd
    assert sample.value == Decimal("41.3")
    assert sample.is_daily_total is True
    assert sample.recorded_at == datetime(2026, 9, 5, tzinfo=timezone.utc)
    assert sample.zone_offset is None
    assert sample.user_id == user_id
    assert sample.provider == "google"


def test_sync_data_type_routes_the_new_type() -> None:
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
