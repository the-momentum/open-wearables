"""Tests for Suunto247Data — focused on resting_heart_rate emission from sleep."""

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.suunto.data_247 import Suunto247Data
from app.services.providers.suunto.strategy import SuuntoStrategy


@pytest.fixture
def data_247() -> Suunto247Data:
    instance = SuuntoStrategy().data_247
    assert isinstance(instance, Suunto247Data)
    return instance


@pytest.fixture
def base_sleep() -> dict:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "provider": "suunto",
        "is_nap": False,
        "min_heart_rate_bpm": 52.0,
        "suunto_sleep_id": 12345,
    }


@pytest.fixture
def timeseries_service_mock() -> Generator[MagicMock, None, None]:
    with patch(
        "app.services.providers.suunto.data_247.timeseries_service",
    ) as mock:
        yield mock


class TestSuuntoSleepNormalization:
    def test_normalize_sleep_extracts_hr_extremes(self, data_247: Suunto247Data) -> None:
        raw = {
            "timestamp": "2026-05-17T02:13:00.000+02:00",
            "entryData": {
                "BedtimeStart": "2026-05-17T02:13:00.000+02:00",
                "BedtimeEnd": "2026-05-17T09:19:00.000+02:00",
                "Duration": 25560.0,
                "DeepSleepDuration": 5610.0,
                "LightSleepDuration": 17970.0,
                "REMSleepDuration": 1710.0,
                "HRAvg": 67.0,
                "HRMin": 52.0,
                "SleepQualityScore": 75,
                "IsNap": False,
                "SleepId": 1778976780,
            },
        }
        result = data_247.normalize_sleep(raw, uuid4())

        assert result["avg_heart_rate_bpm"] == 67.0
        assert result["min_heart_rate_bpm"] == 52.0
        assert result["is_nap"] is False


class TestSuuntoRestingHeartRatePersistence:
    def test_emits_rhr_sample_for_non_nap_sleep_with_hr_min(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        db = MagicMock()
        recorded_at = datetime(2026, 5, 17, 9, 19, tzinfo=timezone.utc)

        data_247._persist_resting_heart_rate(db, base_sleep["user_id"], base_sleep, recorded_at)

        timeseries_service_mock.bulk_create_samples.assert_called_once()
        samples = timeseries_service_mock.bulk_create_samples.call_args[0][1]
        assert len(samples) == 1
        sample = samples[0]
        assert sample.series_type == SeriesType.resting_heart_rate
        assert sample.value == Decimal("52.0")
        assert sample.recorded_at == recorded_at
        assert sample.user_id == base_sleep["user_id"]
        assert sample.source == "suunto"
        assert sample.external_id == "12345"
        db.commit.assert_called_once()

    def test_skips_nap_sessions(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        base_sleep["is_nap"] = True

        data_247._persist_resting_heart_rate(
            MagicMock(),
            base_sleep["user_id"],
            base_sleep,
            datetime.now(timezone.utc),
        )

        timeseries_service_mock.bulk_create_samples.assert_not_called()

    def test_skips_when_hr_min_missing(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        base_sleep["min_heart_rate_bpm"] = None

        data_247._persist_resting_heart_rate(
            MagicMock(),
            base_sleep["user_id"],
            base_sleep,
            datetime.now(timezone.utc),
        )

        timeseries_service_mock.bulk_create_samples.assert_not_called()

    def test_swallows_service_errors_and_rolls_back(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        timeseries_service_mock.bulk_create_samples.side_effect = RuntimeError("db down")
        db = MagicMock()

        data_247._persist_resting_heart_rate(
            db,
            base_sleep["user_id"],
            base_sleep,
            datetime.now(timezone.utc),
        )

        timeseries_service_mock.bulk_create_samples.assert_called_once()
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
