"""Tests for Oura247Data.save_sleep_data — per-night scalar series persistence."""

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.schemas.providers.oura.imports import OuraIntervalData
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.strategy import OuraStrategy


@pytest.fixture
def data_247() -> Oura247Data:
    instance = OuraStrategy().data_247
    assert isinstance(instance, Oura247Data)
    return instance


@pytest.fixture
def timeseries_service_mock() -> Generator[MagicMock, None, None]:
    with patch("app.services.providers.oura.data_247.timeseries_service") as mock:
        yield mock


@pytest.fixture(autouse=True)
def event_record_service_mock() -> Generator[MagicMock, None, None]:
    with patch("app.services.providers.oura.data_247.event_record_service") as mock:
        yield mock


def _normalized_sleep(user_id: object, **overrides: object) -> dict:
    base = {
        "id": uuid4(),
        "user_id": user_id,
        "provider": "oura",
        "start_time": "2024-01-15T23:00:00+00:00",
        "end_time": "2024-01-16T07:00:00+00:00",
        "duration_seconds": 28800,
        "efficiency_percent": 88.0,
        "is_nap": False,
        "stages": {"deep_seconds": 5400, "light_seconds": 14400, "rem_seconds": 7200, "awake_seconds": 1800},
        "stage_timestamps": [],
        "average_breath": 15.5,
        "average_heart_rate": 55.0,
        "average_hrv": 45,
        "lowest_heart_rate": 48,
        "heart_rate": None,
        "hrv": None,
        "oura_sleep_id": "sleep-abc123",
    }
    base.update(overrides)
    return base


class TestOuraSleepScalarSeriesPersistence:
    def test_persists_average_hrv_as_distinct_series_type(
        self,
        data_247: Oura247Data,
        timeseries_service_mock: MagicMock,
    ) -> None:
        user_id = uuid4()
        db = MagicMock()

        data_247.save_sleep_data(db, user_id, [_normalized_sleep(user_id)])

        samples = [
            call.args[1][0]
            for call in timeseries_service_mock.bulk_create_samples.call_args_list
            if call.args[1][0].series_type
            in {
                SeriesType.respiratory_rate,
                SeriesType.resting_heart_rate,
                SeriesType.heart_rate_variability_rmssd_average,
            }
        ]
        by_type = {s.series_type: s for s in samples}

        assert by_type.keys() == {
            SeriesType.respiratory_rate,
            SeriesType.resting_heart_rate,
            SeriesType.heart_rate_variability_rmssd_average,
        }
        hrv_sample = by_type[SeriesType.heart_rate_variability_rmssd_average]
        assert hrv_sample.value == Decimal("45")
        assert hrv_sample.recorded_at == datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert hrv_sample.user_id == user_id
        assert hrv_sample.source == "oura"

    def test_average_hrv_scalar_does_not_collide_with_interval_hrv_sample(
        self,
        data_247: Oura247Data,
        timeseries_service_mock: MagicMock,
    ) -> None:
        """The nightly-average HRV write and the first 5-minute interval HRV sample share
        the same recorded_at (sleep start); they must use different SeriesTypes or the
        DB upsert on (data_source_id, series_type_definition_id, recorded_at) would let
        one silently overwrite the other."""
        user_id = uuid4()
        db = MagicMock()
        normalized = _normalized_sleep(
            user_id,
            hrv=OuraIntervalData(interval=300, items=[42.0, 43.0], timestamp="2024-01-15T23:00:00+00:00"),
        )

        data_247.save_sleep_data(db, user_id, [normalized])

        all_samples = [
            sample for call in timeseries_service_mock.bulk_create_samples.call_args_list for sample in call.args[1]
        ]
        same_timestamp_samples = [
            s for s in all_samples if s.recorded_at == datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        ]
        series_types_at_start = {s.series_type for s in same_timestamp_samples}

        assert SeriesType.heart_rate_variability_rmssd in series_types_at_start
        assert SeriesType.heart_rate_variability_rmssd_average in series_types_at_start
        # Distinct series types at the same timestamp -> distinct DB rows, no upsert collision.
        assert len(same_timestamp_samples) == len({id(s) for s in same_timestamp_samples})
