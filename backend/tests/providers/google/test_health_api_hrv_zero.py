"""A zero standard deviation is not an HRV measurement.

Google's Health API returns ``standardDeviationMilliseconds: 0`` for devices that do not
compute SDNN, rather than omitting the field. Stored as a sample, that reads as a real
measurement and drags every average built on the series — silently, because the data is
*there*. Observed on a production deployment: 19,503 consecutive samples, all exactly
0.000, over eleven months, on a series that had carried real values (mean 53.2 ms) from a
previous device. RMSSD from the same payload never comes as 0 (172,022 samples, none zero),
which is the expected shape: a dispersion statistic of exactly zero would mean every
interbeat interval was identical.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.providers.google.health_api import SeriesType
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.health_api.metrics.heart import HEART_METRICS


def _hrv_metric() -> Any:
    return next(m for m in HEART_METRICS if m.data_type == "heart-rate-variability")


def _point(sdnn: Any) -> dict[str, Any]:
    hrv: dict[str, Any] = {
        "sampleTime": {"physicalTime": "2026-09-09T04:34:36Z", "utcOffset": "7200s"},
        "rootMeanSquareOfSuccessiveDifferencesMilliseconds": 38.9,
    }
    if sdnn is not None:
        hrv["standardDeviationMilliseconds"] = sdnn
    return {"heartRateVariability": hrv, "dataSource": {}}


def _samples(sdnn: Any) -> list[Any]:
    handler = GoogleHealth247Data(MagicMock(), MagicMock(), "https://health.googleapis.com")
    with patch.object(handler, "_fetch_points", return_value=[_point(sdnn)]):
        return handler._native_samples(
            MagicMock(),
            uuid4(),
            _hrv_metric(),
            datetime(2026, 9, 9, tzinfo=timezone.utc),
            datetime(2026, 9, 10, tzinfo=timezone.utc),
        )


def test_zero_sdnn_is_dropped_and_rmssd_is_kept() -> None:
    series = [s.series_type_id if hasattr(s, "series_type_id") else s.series_type for s in _samples(0)]
    assert SeriesType.heart_rate_variability_rmssd in series
    assert SeriesType.heart_rate_variability_sdnn not in series


def test_a_real_sdnn_still_comes_through() -> None:
    series = [s.series_type_id if hasattr(s, "series_type_id") else s.series_type for s in _samples(41.7)]
    assert SeriesType.heart_rate_variability_sdnn in series


def test_a_missing_sdnn_field_is_unchanged() -> None:
    series = [s.series_type_id if hasattr(s, "series_type_id") else s.series_type for s in _samples(None)]
    assert SeriesType.heart_rate_variability_sdnn not in series
    assert SeriesType.heart_rate_variability_rmssd in series
