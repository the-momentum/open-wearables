"""Sleep temperature derivations: Google reports a nightly value and a baseline, not a deviation."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.config import settings
from app.schemas.enums import DeviceType, SeriesType
from app.schemas.providers.google import DataTypeMetric
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.metrics import METRICS

USER_ID = uuid4()
WINDOW = (datetime(2026, 5, 1, tzinfo=timezone.utc), datetime(2026, 5, 3, tzinfo=timezone.utc))
POINT = {
    "dailySleepTemperatureDerivations": {
        "date": {"year": 2026, "month": 5, "day": 2},
        "nightlyTemperatureCelsius": 35.4,
        "baselineTemperatureCelsius": 35.6,
        "relativeNightlyStddev30dCelsius": 0.18,
    }
}


@pytest.fixture
def data_247() -> GoogleHealth247Data:
    return GoogleHealth247Data(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="https://x")


def _metric() -> DataTypeMetric:
    return next(m for m in METRICS if m.data_type == "daily-sleep-temperature-derivations")


def test_the_night_yields_its_temperature_and_its_deviation_from_baseline(data_247: GoogleHealth247Data) -> None:
    with patch.object(data_247, "_fetch_points", return_value=iter([POINT])):
        samples = data_247._native_samples(MagicMock(), USER_ID, _metric(), *WINDOW)

    by_type = {sample.series_type: float(sample.value) for sample in samples}
    assert by_type[SeriesType.skin_temperature] == 35.4
    # Google publishes no deviation of its own; it is the night against the user's baseline.
    assert round(by_type[SeriesType.skin_temperature_deviation], 2) == -0.2


def test_a_night_without_a_baseline_still_yields_its_temperature(data_247: GoogleHealth247Data) -> None:
    point = {
        "dailySleepTemperatureDerivations": {
            k: v for k, v in POINT["dailySleepTemperatureDerivations"].items() if k != "baselineTemperatureCelsius"
        }
    }

    with patch.object(data_247, "_fetch_points", return_value=iter([point])):
        samples = data_247._native_samples(MagicMock(), USER_ID, _metric(), *WINDOW)

    assert [sample.series_type for sample in samples] == [SeriesType.skin_temperature]


def test_the_deviation_keeps_the_device_of_the_night_it_comes_from(
    data_247: GoogleHealth247Data, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_use_reconcile", False)
    point = {**POINT, "dataSource": {"device": {"displayName": "Charge 6", "formFactor": "FITNESS_BAND"}}}

    with patch.object(data_247, "_fetch_points", return_value=iter([point])):
        samples = data_247._native_samples(MagicMock(), USER_ID, _metric(), *WINDOW)

    assert len(samples) == 2
    assert {(sample.device_model, sample.device_type) for sample in samples} == {("Charge 6", DeviceType.BAND)}
