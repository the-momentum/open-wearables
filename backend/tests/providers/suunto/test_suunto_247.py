"""Tests for Suunto247Data — focused on resting_heart_rate emission from sleep."""

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
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


def _normalized_sleep(**overrides: Any) -> dict[str, Any]:
    """A normalized sleep dict shaped exactly as ``normalize_sleep`` emits one."""
    base: dict[str, Any] = {
        "id": uuid4(),
        "suunto_sleep_id": 1780782000,
        "start_time": "2026-06-06T23:40:00+02:00",
        "end_time": "2026-06-07T06:12:00+02:00",
        "duration_seconds": 23520,
        "efficiency_percent": 77,
        "is_nap": False,
        "min_heart_rate_bpm": None,
        "stages": {"deep_seconds": 7320, "light_seconds": 10950, "rem_seconds": 5220, "awake_seconds": 30},
    }
    base.update(overrides)
    return base


class TestSuuntoSleepSyncStats:
    """The sleep sync loop must skip unsaveable sessions and report accurate
    (saved, skipped) counts, so a fully-dropped backfill is never reported as a
    successful sync."""

    @patch("app.services.providers.suunto.data_247.event_record_service")
    def test_save_sleep_data_reports_success(self, mock_event: MagicMock, data_247: Suunto247Data) -> None:
        assert data_247.save_sleep_data(MagicMock(), uuid4(), _normalized_sleep()) is True
        mock_event.create_or_merge_sleep.assert_called_once()

    @patch("app.services.providers.suunto.data_247.event_record_service")
    def test_save_sleep_data_reports_skip_for_missing_window(
        self, mock_event: MagicMock, data_247: Suunto247Data
    ) -> None:
        skipped = data_247.save_sleep_data(MagicMock(), uuid4(), _normalized_sleep(start_time=None, end_time=None))

        assert skipped is False
        mock_event.create_or_merge_sleep.assert_not_called()

    @patch("app.services.providers.suunto.data_247.event_record_service")
    def test_load_and_save_sleep_counts_saved_and_skipped(self, mock_event: MagicMock, data_247: Suunto247Data) -> None:
        saveable = {
            "timestamp": "2026-06-06T23:40:00+02:00",
            "entryData": {
                "BedtimeStart": "2026-06-06T23:40:00+02:00",
                "BedtimeEnd": "2026-06-07T06:12:00+02:00",
                "Duration": 23520.0,
                "SleepId": 1,
            },
        }
        unsaveable = {"timestamp": "2026-06-07T13:00:00+02:00", "entryData": {"Duration": 0.0, "SleepId": 2}}

        with patch.object(data_247, "get_sleep_data", return_value=[saveable, unsaveable]):
            saved, skipped = data_247.load_and_save_sleep(
                MagicMock(), uuid4(), datetime.now(timezone.utc), datetime.now(timezone.utc)
            )

        assert (saved, skipped) == (1, 1)

    def test_load_and_save_all_surfaces_skipped_count(self, data_247: Suunto247Data) -> None:
        with (
            patch.object(data_247, "load_and_save_sleep", return_value=(2, 3)),
            patch.object(data_247, "load_and_save_recovery", return_value=0),
            patch.object(data_247, "get_activity_samples", return_value=[]),
            patch.object(data_247, "get_daily_activity_statistics", return_value=[]),
        ):
            results = data_247.load_and_save_all(MagicMock(), uuid4())

        assert results["sleep_sessions_synced"] == 2
        assert results["sleep_sessions_skipped"] == 3
