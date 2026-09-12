"""Tests for Suunto247Data — focused on resting_heart_rate emission from sleep."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.suunto.data_247 import Suunto247Data
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.utils.dates import parse_iso_datetime


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

    def test_normalize_sleep_converts_spo2_fraction_to_percent(self, data_247: Suunto247Data) -> None:
        raw = {"entryData": {"BedtimeStart": "2025-01-05T23:00:00.000+01:00", "MaxSpo2": 0.98}}

        assert data_247.normalize_sleep(raw, uuid4())["max_spo2_percent"] == 98.0

    def test_normalize_sleep_leaves_spo2_already_in_percent(self, data_247: Suunto247Data) -> None:
        raw = {"entryData": {"BedtimeStart": "2025-01-05T23:00:00.000+01:00", "MaxSpo2": 98.0}}

        assert data_247.normalize_sleep(raw, uuid4())["max_spo2_percent"] == 98.0


class TestSuuntoSleepAwakeTime:
    """Awake time comes from ``WakeAfterSleepOnsetDuration`` + ``WakeBeforeOffBedDuration``."""

    def test_awake_excludes_onset_latency(self, data_247: Suunto247Data) -> None:
        # Duration exceeds the stage total by the wake window plus the onset latency.
        raw = {
            "timestamp": "2025-01-05T23:00:00.000+01:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:00:00.000+01:00",
                "BedtimeEnd": "2025-01-06T07:00:00.000+01:00",
                "Duration": 28800.0,
                "DeepSleepDuration": 7200.0,
                "LightSleepDuration": 14400.0,
                "REMSleepDuration": 5400.0,
                "WakeAfterSleepOnsetDuration": 1200.0,
                "WakeBeforeOffBedDuration": 0.0,
                "SleepOnsetLatencyDuration": 600.0,
                "SleepQualityScore": 70,
                "IsNap": False,
                "SleepId": 1,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["stages"]["awake_seconds"] == 1200

    def test_nap_payload_reports_no_awake_time(self, data_247: Suunto247Data) -> None:
        """Suunto scores neither stages nor quality for a session it calls a nap.

        It can later revise the same SleepId into a full night, so the nap normalizes
        to the zero awake time it reports rather than to its whole Duration.
        """
        raw = {
            "timestamp": "2025-01-05T23:00:00.000+01:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:00:00.000+01:00",
                "BedtimeEnd": "2025-01-06T00:00:00.000+01:00",
                "Duration": 3600.0,
                "DeepSleepDuration": 0.0,
                "LightSleepDuration": 0.0,
                "REMSleepDuration": 0.0,
                "WakeAfterSleepOnsetDuration": 0.0,
                "WakeBeforeOffBedDuration": 0.0,
                "IsNap": True,
                "SleepId": 2,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["stages"]["awake_seconds"] == 0
        assert result["duration_seconds"] == 3600
        assert result["is_nap"] is True
        assert result["efficiency_percent"] is None

    def test_awake_is_zero_when_stages_fill_the_whole_duration(self, data_247: Suunto247Data) -> None:
        raw = {
            "timestamp": "2025-01-05T23:00:00.000+01:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:00:00.000+01:00",
                "BedtimeEnd": "2025-01-06T07:00:00.000+01:00",
                "Duration": 28800.0,
                "DeepSleepDuration": 7200.0,
                "LightSleepDuration": 14400.0,
                "REMSleepDuration": 7200.0,
                "WakeAfterSleepOnsetDuration": 0.0,
                "WakeBeforeOffBedDuration": 0.0,
                "SleepQualityScore": 90,
                "IsNap": False,
                "SleepId": 3,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["stages"]["awake_seconds"] == 0
        assert result["efficiency_percent"] == 90

    def test_awake_sums_both_reported_wake_windows(self, data_247: Suunto247Data) -> None:
        raw = {
            "timestamp": "2025-01-05T23:00:00.000+01:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:00:00.000+01:00",
                "BedtimeEnd": "2025-01-06T07:00:00.000+01:00",
                "Duration": 28800.0,
                "DeepSleepDuration": 7200.0,
                "LightSleepDuration": 14400.0,
                "REMSleepDuration": 5400.0,
                "WakeAfterSleepOnsetDuration": 600.0,
                "WakeBeforeOffBedDuration": 600.0,
                "SleepQualityScore": 80,
                "IsNap": False,
                "SleepId": 4,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["stages"]["awake_seconds"] == 1200

    def test_awake_defaults_to_zero_when_wake_fields_absent(self, data_247: Suunto247Data) -> None:
        raw = {
            "timestamp": "2025-01-05T23:00:00.000+01:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:00:00.000+01:00",
                "BedtimeEnd": "2025-01-06T07:00:00.000+01:00",
                "Duration": 28800.0,
                "DeepSleepDuration": 7200.0,
                "LightSleepDuration": 14400.0,
                "REMSleepDuration": 5400.0,
                "SleepId": 5,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["stages"]["awake_seconds"] == 0


class TestSuuntoSleepWindowFallback:
    """Suunto documents an explicit in-bed window (``BedtimeStart``/``BedtimeEnd``).

    Devices that omit the pair (e.g. Suunto 5 Peak) report onset only as the wrapper
    ``timestamp``, so the window falls back to that plus ``Duration`` rather than
    dropping the session."""

    def test_prefers_explicit_bedtime_window_when_present(self, data_247: Suunto247Data) -> None:
        # Window differs from timestamp+Duration, so preferring it is observable.
        raw = {
            "timestamp": "2025-01-05T23:29:00.000+02:00",
            "entryData": {
                "BedtimeStart": "2025-01-05T23:20:00.000+02:00",
                "BedtimeEnd": "2025-01-06T08:30:00.000+02:00",
                "Duration": 23520.0,
            },
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert parse_iso_datetime(result["start_time"]) == parse_iso_datetime("2025-01-05T23:20:00.000+02:00")
        assert parse_iso_datetime(result["end_time"]) == parse_iso_datetime("2025-01-06T08:30:00.000+02:00")

    def test_falls_back_to_wrapper_timestamp_when_bedtimes_absent(self, data_247: Suunto247Data) -> None:
        raw = {"timestamp": "2026-06-06T23:40:00.000+02:00", "entryData": {"Duration": 23520.0}}

        result = data_247.normalize_sleep(raw, uuid4())

        start = parse_iso_datetime(result["start_time"])
        end = parse_iso_datetime(result["end_time"])
        assert start == parse_iso_datetime("2026-06-06T23:40:00.000+02:00")
        assert end - start == timedelta(seconds=23520)

    def test_returns_no_window_when_no_timestamp_at_all(self, data_247: Suunto247Data) -> None:
        raw = {"entryData": {"Duration": 3600.0, "SleepId": 1}}

        result = data_247.normalize_sleep(raw, uuid4())

        assert result["start_time"] is None
        assert result["end_time"] is None

    def test_reconstructs_start_when_only_bedtime_end_present(self, data_247: Suunto247Data) -> None:
        raw = {"entryData": {"BedtimeEnd": "2025-01-06T07:00:00.000+01:00", "Duration": 28800.0}}

        result = data_247.normalize_sleep(raw, uuid4())

        assert parse_iso_datetime(result["end_time"]) == parse_iso_datetime("2025-01-06T07:00:00.000+01:00")
        assert parse_iso_datetime(result["start_time"]) == parse_iso_datetime("2025-01-05T23:00:00.000+01:00")

    def test_reconstructs_end_when_only_bedtime_start_present(self, data_247: Suunto247Data) -> None:
        raw = {
            "timestamp": "2025-01-05T23:29:00.000+02:00",
            "entryData": {"BedtimeStart": "2025-01-05T23:20:00.000+02:00", "Duration": 3600.0},
        }

        result = data_247.normalize_sleep(raw, uuid4())

        assert parse_iso_datetime(result["start_time"]) == parse_iso_datetime("2025-01-05T23:20:00.000+02:00")
        assert parse_iso_datetime(result["end_time"]) == parse_iso_datetime("2025-01-06T00:20:00.000+02:00")


class TestSuuntoSaveSleepSkipSignal:
    def test_returns_false_for_zero_length_window(
        self, data_247: Suunto247Data, timeseries_service_mock: MagicMock
    ) -> None:
        normalized = {
            "id": uuid4(),
            "start_time": "2026-06-06T23:40:00.000+02:00",
            "end_time": "2026-06-06T23:40:00.000+02:00",
            "duration_seconds": 0,
            "stages": {},
            "is_nap": False,
            "suunto_sleep_id": 1,
        }

        with patch("app.services.providers.suunto.data_247.event_record_service") as event_record_service_mock:
            result = data_247.save_sleep_data(MagicMock(), uuid4(), normalized)

        assert result is False
        event_record_service_mock.create_or_merge_sleep.assert_not_called()

    def test_saves_window_whose_edges_disagree_on_tz_awareness(
        self, data_247: Suunto247Data, timeseries_service_mock: MagicMock
    ) -> None:
        # A naive start against an offset-aware end must compare, not raise. The naive
        # edge borrows the sibling's offset rather than being assumed UTC, so the stored
        # instant stays in the device's zone.
        normalized = {
            "id": uuid4(),
            "start_time": "2025-01-05T23:00:00.000",
            "end_time": "2025-01-06T07:00:00.000+01:00",
            "duration_seconds": 28800,
            "stages": {},
            "is_nap": True,
            "suunto_sleep_id": 6,
            "efficiency_percent": None,
        }

        with patch("app.services.providers.suunto.data_247.event_record_service") as event_record_service_mock:
            result = data_247.save_sleep_data(MagicMock(), uuid4(), normalized)

        assert result is True
        record = event_record_service_mock.create_or_merge_sleep.call_args[0][2]
        assert record.start_datetime == parse_iso_datetime("2025-01-05T23:00:00.000+01:00")
        assert record.end_datetime == parse_iso_datetime("2025-01-06T07:00:00.000+01:00")


class TestSuuntoSleepSeriesPersistence:
    def test_emits_rhr_sample_for_non_nap_sleep_with_hr_min(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        db = MagicMock()
        recorded_at = datetime(2026, 5, 17, 9, 19, tzinfo=timezone.utc)

        data_247._persist_sleep_series(db, base_sleep["user_id"], base_sleep, recorded_at)

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
        assert sample.is_daily_total is True
        db.commit.assert_called_once()

    def test_emits_hrv_and_spo2_alongside_rhr(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        base_sleep["avg_hrv_ms"] = 49.0
        base_sleep["max_spo2_percent"] = 98.0

        data_247._persist_sleep_series(
            MagicMock(),
            base_sleep["user_id"],
            base_sleep,
            datetime(2025, 1, 6, 7, 0, tzinfo=timezone.utc),
        )

        samples = timeseries_service_mock.bulk_create_samples.call_args[0][1]
        by_type = {s.series_type: s for s in samples}
        assert by_type.keys() == {
            SeriesType.resting_heart_rate,
            SeriesType.heart_rate_variability_rmssd,
            SeriesType.oxygen_saturation,
        }
        assert by_type[SeriesType.heart_rate_variability_rmssd].value == Decimal("49.0")
        assert by_type[SeriesType.oxygen_saturation].value == Decimal("98.0")
        assert all(s.is_daily_total is True for s in samples)

    def test_skips_nap_sessions(
        self,
        data_247: Suunto247Data,
        base_sleep: dict,
        timeseries_service_mock: MagicMock,
    ) -> None:
        base_sleep["is_nap"] = True

        data_247._persist_sleep_series(
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

        data_247._persist_sleep_series(
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

        data_247._persist_sleep_series(
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
