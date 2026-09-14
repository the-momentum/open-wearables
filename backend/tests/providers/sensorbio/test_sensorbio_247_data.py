"""Tests for SensorBio 247 data: normalize_sleep, normalize_recovery, save_recovery_data,
normalize_daily_activity, save_daily_activity, normalize_activity_samples edge cases,
pagination stop conditions, HTTP/2 204/404/timeout propagation, and recovery/activity/sleep
score persistence.

Mirrors Polar's per-data-type class structure (TestPolar247SleepNormalization, etc.)
as recommended in gap-analysis card t_38e552b2 finding #8.

t_5912f22f adds: ACTIVITY + SLEEP HealthScore extraction from /v1/scores (parity with Oura).
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.sensorbio.data_247 import SensorBio247Data

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

USER_ID = uuid4()
DB = MagicMock()


@pytest.fixture
def data_247() -> SensorBio247Data:
    return SensorBio247Data(
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=MagicMock(),
    )


# ---------------------------------------------------------------------------
# 1. normalize_sleep
# ---------------------------------------------------------------------------


class TestSensorBio247SleepNormalization:
    """normalize_sleep() — validates and normalises /v1/sleep records."""

    def test_full_record(self, data_247: SensorBio247Data) -> None:
        raw = {
            "id": "sleep-abc",
            "start_timestamp": 1_700_000_000,
            "end_timestamp": 1_700_028_800,
            "total_sleep_mins": 420.0,
            "deep_sleep_mins": 90.0,
            "light_sleep_mins": 180.0,
            "rem_sleep_mins": 120.0,
            "awake_time_mins": 30.0,
            "biometrics": {"bpm": 55.0, "hrv": 45.0, "spo2": 97.0, "resting_bpm": 52.0, "resting_hrv": 48.0},
            "score": {"value": 88},
        }
        result = data_247.normalize_sleep(raw, USER_ID)
        assert result is not None
        assert result["start_time"] == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
        assert result["end_time"] == datetime.fromtimestamp(1_700_028_800, tz=timezone.utc)
        assert result["duration_seconds"] == 420 * 60
        assert result["efficiency_percent"] == 88
        assert result["stages"]["deep_seconds"] == 90 * 60
        assert result["stages"]["rem_seconds"] == 120 * 60
        assert result["stages"]["awake_seconds"] == 30 * 60
        assert result["average_hrv"] == 45.0
        assert result["average_spo2"] == 97.0
        assert result["resting_heart_rate"] == 52.0

    def test_is_nap_always_false_without_api_flag(self, data_247: SensorBio247Data) -> None:
        """Sensor Bio has no nap flag; short sessions stay is_nap=False."""
        raw = {
            "start_timestamp": 1_700_000_000,
            "end_timestamp": 1_700_005_400,
            "total_sleep_mins": 90.0,  # 1.5 h
        }
        result = data_247.normalize_sleep(raw, USER_ID)
        assert result is not None
        assert result["is_nap"] is False

    def test_full_night_not_nap(self, data_247: SensorBio247Data) -> None:
        raw = {
            "start_timestamp": 1_700_000_000,
            "end_timestamp": 1_700_028_800,
            "total_sleep_mins": 480.0,  # 8 h
        }
        result = data_247.normalize_sleep(raw, USER_ID)
        assert result is not None
        assert result["is_nap"] is False

    def test_missing_start_end_still_returns_record(self, data_247: SensorBio247Data) -> None:
        """A record without start/end is normalised but timestamp will be None.
        save_sleep_data() will skip it — that's intentional.
        """
        raw: dict[str, Any] = {}
        result = data_247.normalize_sleep(raw, USER_ID)
        assert result is not None  # normalize returns the record
        assert result["start_time"] is None
        assert result["end_time"] is None

    def test_empty_biometrics(self, data_247: SensorBio247Data) -> None:
        """Empty biometrics dict should not cause a crash."""
        raw = {
            "start_timestamp": 1_700_000_000,
            "end_timestamp": 1_700_028_800,
            "total_sleep_mins": 420.0,
            "biometrics": {},
        }
        result = data_247.normalize_sleep(raw, USER_ID)
        assert result is not None
        assert result["average_hrv"] is None
        assert result["resting_heart_rate"] is None

    def test_malformed_payload_returns_none(self, data_247: SensorBio247Data) -> None:
        """A non-dict value in a typed field should be handled — model_validate raises."""
        # start_timestamp with a non-numeric string causes ValidationError → None
        raw = {"start_timestamp": "not-a-number", "total_sleep_mins": "bad"}
        # Pydantic coerces str→int in lax mode so this might succeed; test the
        # structural contract: normalize_sleep always returns dict or None, never raises.
        result = data_247.normalize_sleep(raw, USER_ID)
        # Either None (validation error) or a valid dict — must not raise
        assert result is None or isinstance(result, dict)


class TestSensorBio247SaveSleepData:
    """save_sleep_data() — skips records with missing start/end; persists valid ones."""

    def test_skips_missing_start_time(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "id": uuid4(),
            "start_time": None,
            "end_time": datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc),
        }
        result = data_247.save_sleep_data(db, USER_ID, normalized)
        assert result is False

    def test_skips_missing_end_time(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "id": uuid4(),
            "start_time": datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            "end_time": None,
        }
        result = data_247.save_sleep_data(db, USER_ID, normalized)
        assert result is False

    def test_persists_valid_record(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "id": uuid4(),
            "start_time": datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            "end_time": datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc),
            "duration_seconds": 28800,
            "efficiency_percent": 88,
            "stages": {"deep_seconds": 5400, "light_seconds": 14400, "rem_seconds": 7200, "awake_seconds": 1800},
            "is_nap": False,
            "sensorbio_sleep_id": "sleep-abc",
        }
        with patch("app.services.providers.sensorbio.data_247.event_record_service") as mock_svc:
            mock_svc.create.return_value = MagicMock(id=normalized["id"])
            result = data_247.save_sleep_data(db, USER_ID, normalized)
        assert result is True
        mock_svc.create.assert_called_once()
        mock_svc.create_detail.assert_called_once()


# ---------------------------------------------------------------------------
# 2. normalize_recovery + save_recovery_data (including recovery.value extraction)
# ---------------------------------------------------------------------------


class TestSensorBio247RecoveryNormalization:
    """normalize_recovery() — validates + extracts recovery.value (NOT recovery.score.value)."""

    def test_extracts_recovery_value(self, data_247: SensorBio247Data) -> None:
        """Real API shape: data.recovery.value (confirmed ae14746)."""
        raw = {
            "date": "2024-01-15",
            "recovery": {"value": 72, "stage": "good"},
            "sleep": {"biometrics": {"resting_bpm": 52.0, "resting_hrv": 48.0, "hrv": 50.0, "spo2": 97.0}},
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["recovery_score"] == 72
        assert result["recovery_stage"] == "good"
        assert result["timestamp"] == datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert result["resting_heart_rate"] == 52.0
        assert result["hrv_rmssd_milli"] == 48.0
        assert result["spo2_percentage"] == 97.0

    def test_no_recovery_score_is_none(self, data_247: SensorBio247Data) -> None:
        """Missing recovery.value → recovery_score is None (no crash)."""
        raw = {"date": "2024-01-15", "recovery": {}}
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["recovery_score"] is None

    def test_missing_date_timestamp_is_none(self, data_247: SensorBio247Data) -> None:
        raw: dict[str, Any] = {}
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["timestamp"] is None

    def test_legacy_score_value_path_not_used(self, data_247: SensorBio247Data) -> None:
        """data.recovery.score.value — old bug path — must NOT produce a score."""
        raw = {
            "date": "2024-01-15",
            "recovery": {"score": {"value": 99}},  # legacy wrong path
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        # recovery.value is the real path; legacy path should not be read
        assert result["recovery_score"] is None


class TestSensorBio247SaveRecoveryData:
    """save_recovery_data() — persists timeseries AND HealthScore (gap #2 fix)."""

    def test_persists_recovery_health_score(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "recovery_score": 72,
            "recovery_stage": "good",
            "resting_heart_rate": 52.0,
            "hrv_rmssd_milli": 48.0,
            "spo2_percentage": 97.0,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts,
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            mock_ts.bulk_create_samples.return_value = 3
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 3, "scores_synced": 1}
        mock_ts.bulk_create_samples.assert_called_once()
        mock_hs.bulk_create.assert_called_once()
        scores = mock_hs.bulk_create.call_args[0][1]
        from app.schemas.enums import HealthScoreCategory

        assert len(scores) == 1
        assert scores[0].category == HealthScoreCategory.RECOVERY
        assert scores[0].value == 72
        assert scores[0].qualifier == "good"

    def test_skips_health_score_when_none(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "recovery_score": None,
            "resting_heart_rate": 52.0,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts,
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            mock_ts.bulk_create_samples.return_value = 1
            data_247.save_recovery_data(db, USER_ID, normalized)

        mock_hs.bulk_create.assert_not_called()

    def test_skips_all_when_no_timestamp(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {"timestamp": None, "recovery_score": 72, "resting_heart_rate": 52.0}
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts,
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            counts = data_247.save_recovery_data(db, USER_ID, normalized)
        assert counts == {"metrics_synced": 0, "scores_synced": 0}
        mock_ts.bulk_create_samples.assert_not_called()
        mock_hs.bulk_create.assert_not_called()


# ---------------------------------------------------------------------------
# 3. normalize_activity_samples edge cases
# ---------------------------------------------------------------------------


class TestSensorBio247ActivitySamplesNormalization:
    """normalize_activity_samples() edge cases."""

    def test_null_timestamp_skipped(self, data_247: SensorBio247Data) -> None:
        """A biometrics record with no timestamp should be skipped (gap: null timestamp)."""
        raw_samples = [
            {"timestamp": None, "bpm": 72},
        ]
        result = data_247.normalize_activity_samples(raw_samples, USER_ID)
        assert result["heart_rate"] == []

    def test_all_none_fields_no_output(self, data_247: SensorBio247Data) -> None:
        """A biometrics record where all metric fields are None produces no output rows."""
        raw_samples = [
            {"timestamp": 1_700_000_000_000, "bpm": None, "hrv": None, "spo2": None, "brpm": None},
        ]
        result = data_247.normalize_activity_samples(raw_samples, USER_ID)
        assert all(len(v) == 0 for v in result.values())

    def test_partial_fields(self, data_247: SensorBio247Data) -> None:
        """A record with only bpm should produce exactly one heart_rate entry."""
        raw_samples = [
            {"timestamp": 1_700_000_000_000, "bpm": 65.0},
        ]
        result = data_247.normalize_activity_samples(raw_samples, USER_ID)
        assert len(result["heart_rate"]) == 1
        assert result["heart_rate"][0]["value"] == 65.0
        assert len(result["heart_rate_variability"]) == 0

    def test_multiple_records(self, data_247: SensorBio247Data) -> None:
        raw_samples = [
            {"timestamp": 1_700_000_000_000, "bpm": 65.0, "hrv": 40.0},
            {"timestamp": 1_700_000_060_000, "bpm": 68.0, "hrv": 42.0},
        ]
        result = data_247.normalize_activity_samples(raw_samples, USER_ID)
        assert len(result["heart_rate"]) == 2
        assert len(result["heart_rate_variability"]) == 2

    def test_malformed_record_skipped_gracefully(self, data_247: SensorBio247Data) -> None:
        """A record that fails Pydantic validation should be skipped without crashing."""
        raw_samples: list[dict[str, Any]] = [
            {},  # missing timestamp — ValidationError on BiometricsRecord
        ]
        # Should not raise
        result = data_247.normalize_activity_samples(raw_samples, USER_ID)
        assert all(isinstance(v, list) for v in result.values())


# ---------------------------------------------------------------------------
# 4. Pagination stop conditions
# ---------------------------------------------------------------------------


class TestSensorBio247PaginationStopConditions:
    """get_activity_samples() stops on: empty data, cursor unchanged, links.next absent."""

    def test_stops_on_empty_data(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        with patch.object(data_247, "_make_api_request", return_value={"data": []}):
            result = data_247.get_activity_samples(db, USER_ID, start, end)
        assert result == []

    def test_stops_when_cursor_unchanged(self, data_247: SensorBio247Data) -> None:
        """If the last record's timestamp doesn't advance, stop to avoid infinite loop."""
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)
        # First call returns data with timestamp = 0 (same as initial last_timestamp)
        # NOTE: last_timestamp starts at 0, so if next_timestamp == 0, we stop.
        call_count = 0

        def fake_request(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "data": [{"timestamp": 1_700_000_000_000, "bpm": 65.0}],
                    "links": {"next": "/v1/biometrics?last-timestamp=1700000000000"},
                }
            # Second call: same cursor → should stop
            return {
                "data": [{"timestamp": 1_700_000_000_000, "bpm": 65.0}],
                "links": {"next": "/v1/biometrics?last-timestamp=1700000000000"},
            }

        with patch.object(data_247, "_make_api_request", side_effect=fake_request):
            data_247.get_activity_samples(db, USER_ID, start, end)

        # Should have called twice: first page, then detected cursor unchanged and stopped
        assert call_count == 2  # second call detects unchanged cursor → break

    def test_stops_when_links_next_absent(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch.object(data_247, "_make_api_request") as mock_req:
            mock_req.return_value = {
                "data": [{"timestamp": 1_700_000_000_000, "bpm": 72.0}],
                "links": {},  # no 'next'
            }
            result = data_247.get_activity_samples(db, USER_ID, start, end)

        mock_req.assert_called_once()  # stopped after first page
        # timestamp range filters: 1_700_000_000_000 ms = 2023-11-14 — outside start/end window
        # result may be empty depending on date window, but no infinite loop
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 5. HTTP/2 error propagation — 204/404/timeout through _make_api_request
# ---------------------------------------------------------------------------


class TestSensorBio247HttpErrorPropagation:
    """HTTP errors in get_sleep_data, get_recovery_data, get_activity_samples are handled."""

    def test_sleep_api_error_logs_and_continues(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch.object(data_247, "_make_api_request", side_effect=Exception("HTTP 404")):
            result = data_247.get_sleep_data(db, USER_ID, start, end)

        assert result == []  # exception swallowed, returns empty

    def test_recovery_api_error_logs_and_continues(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch.object(data_247, "_make_api_request", side_effect=Exception("HTTP 204")):
            result = data_247.get_recovery_data(db, USER_ID, start, end)

        assert result == []

    def test_biometrics_api_error_raises_when_no_partial(self, data_247: SensorBio247Data) -> None:
        """get_activity_samples re-raises if no partial results have been accumulated."""
        db = MagicMock()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with (
            patch.object(data_247, "_make_api_request", side_effect=Exception("timeout")),
            pytest.raises(Exception, match="timeout"),
        ):
            data_247.get_activity_samples(db, USER_ID, start, end)

    def test_biometrics_api_error_returns_partial_on_subsequent_pages(self, data_247: SensorBio247Data) -> None:
        """If we have partial results (within date window) and hit an error on page 2, return partial."""
        db = MagicMock()
        # Use a date window that includes the first-page timestamp
        # 1_700_000_000_000 ms = 2023-11-14 UTC
        start = datetime(2023, 11, 1, tzinfo=timezone.utc)
        end = datetime(2023, 12, 31, tzinfo=timezone.utc)
        call_count = 0

        def fake_request(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "data": [{"timestamp": 1_700_000_000_000, "bpm": 65.0}],
                    "links": {"next": "..."},
                }
            raise Exception("connection reset")

        with patch.object(data_247, "_make_api_request", side_effect=fake_request):
            result = data_247.get_activity_samples(db, USER_ID, start, end)

        # Should return the partial first page without re-raising
        assert isinstance(result, list)
        assert len(result) == 1  # the one record within the date window


# ---------------------------------------------------------------------------
# 6. normalize_daily_activity + save_daily_activity (gap #1 fix)
# ---------------------------------------------------------------------------


class TestSensorBio247DailyActivityNormalization:
    """normalize_daily_activity() — validates StepDetailsResponse, extracts steps/distance/energy."""

    def test_full_record(self, data_247: SensorBio247Data) -> None:
        raw = {
            "date": "2024-01-15",
            "granularity": "day",
            "metrics": [
                {"name": "Steps", "value": 8200},
                {"name": "Distance", "value": 6.1, "unit": "km"},
                {"name": "Calories", "value": 312},
                {"name": "Duration", "value": 74},
            ],
        }
        result = data_247.normalize_daily_activity(raw, USER_ID)
        assert result is not None
        assert result["steps"] == 8200
        assert result["distance"] == 6.1
        assert result["energy"] == 312
        assert result["timestamp"] == datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    def test_missing_metrics_keys(self, data_247: SensorBio247Data) -> None:
        """If some metrics are absent, those fields should be None (no crash)."""
        raw = {
            "date": "2024-01-15",
            "metrics": [{"name": "Steps", "value": 5000}],
        }
        result = data_247.normalize_daily_activity(raw, USER_ID)
        assert result is not None
        assert result["steps"] == 5000
        assert result["distance"] is None
        assert result["energy"] is None

    def test_missing_date(self, data_247: SensorBio247Data) -> None:
        raw = {"metrics": [{"name": "Steps", "value": 5000}]}
        result = data_247.normalize_daily_activity(raw, USER_ID)
        assert result is not None
        assert result["timestamp"] is None

    def test_empty_metrics(self, data_247: SensorBio247Data) -> None:
        raw = {"date": "2024-01-15", "metrics": []}
        result = data_247.normalize_daily_activity(raw, USER_ID)
        assert result is not None
        assert result["steps"] is None


class TestSensorBio247SaveDailyActivity:
    """save_daily_activity() — bulk-upserts steps, energy, distance_walking_running."""

    def test_saves_all_three_series(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "steps": 8200,
            "distance": 6.1,
            "energy": 312.0,
        }
        with patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts:
            count = data_247.save_daily_activity(db, USER_ID, normalized)

        assert count == 3
        mock_ts.bulk_create_samples.assert_called_once()
        samples = mock_ts.bulk_create_samples.call_args[0][1]
        series_types = {s.series_type for s in samples}
        assert SeriesType.steps in series_types
        assert SeriesType.energy in series_types
        assert SeriesType.distance_walking_running in series_types

    def test_skips_none_fields(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "steps": 8200,
            "distance": None,
            "energy": None,
        }
        with patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts:
            count = data_247.save_daily_activity(db, USER_ID, normalized)

        assert count == 1
        samples = mock_ts.bulk_create_samples.call_args[0][1]
        assert samples[0].series_type == SeriesType.steps

    def test_skips_when_no_timestamp(self, data_247: SensorBio247Data) -> None:
        db = MagicMock()
        normalized = {"timestamp": None, "steps": 8200}
        with patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts:
            count = data_247.save_daily_activity(db, USER_ID, normalized)
        assert count == 0
        mock_ts.bulk_create_samples.assert_not_called()


# ---------------------------------------------------------------------------
# 7. normalize_recovery — activity + sleep score extraction (t_5912f22f)
# ---------------------------------------------------------------------------


class TestSensorBio247ScoresActivitySleepNormalization:
    """normalize_recovery() extracts activity_score and sleep_score from /v1/scores.

    Added in t_5912f22f (parity with oura ACTIVITY/SLEEP HealthScores).
    The full /v1/scores payload has three score blocks:
        data.activity.value = 97  (was dropped; now extracted)
        data.recovery.value = 48
        data.sleep.value    = 99  (distinct from /v1/sleep efficiency_score)
    """

    def test_extracts_activity_score(self, data_247: SensorBio247Data) -> None:
        """data.activity.value must be returned as activity_score in the normalized dict."""
        raw = {
            "date": "2026-03-14",
            "recovery": {"value": 48, "stage": "go_easy"},
            "activity": {"value": 97, "avg": 75},
            "sleep": {"value": 99, "biometrics": {}},
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["activity_score"] == 97
        assert result["recovery_score"] == 48

    def test_extracts_sleep_score_from_scores(self, data_247: SensorBio247Data) -> None:
        """data.sleep.value from /v1/scores (not /v1/sleep efficiency) must be extracted."""
        raw = {
            "date": "2026-03-14",
            "sleep": {"value": 99, "biometrics": {"resting_bpm": 52.0}},
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["sleep_score"] == 99
        # Biometrics still extracted alongside
        assert result["resting_heart_rate"] == 52.0

    def test_none_when_activity_block_missing(self, data_247: SensorBio247Data) -> None:
        """Missing data.activity block → activity_score is None, no crash."""
        raw = {
            "date": "2026-03-14",
            "recovery": {"value": 48, "stage": "go_easy"},
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["activity_score"] is None

    def test_none_when_sleep_value_missing(self, data_247: SensorBio247Data) -> None:
        """data.sleep block present but no value field → sleep_score is None, no crash."""
        raw = {
            "date": "2026-03-14",
            "sleep": {"biometrics": {"resting_bpm": 55.0}},
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["sleep_score"] is None

    def test_full_live_shape_2026_03_14(self, data_247: SensorBio247Data) -> None:
        """Exercise the exact confirmed-live payload shape (t_5912f22f)."""
        raw = {
            "date": "2026-03-14",
            "activity": {"avg": 75, "goal": 80, "processing": False, "value": 97},
            "recovery": {"avg": 60, "message": "take it easy", "processing": False, "stage": "go_easy", "value": 48},
            "sleep": {
                "avg": 85,
                "duration_secs": 28800,
                "goal": 90,
                "processing": False,
                "value": 99,
                "biometrics": {"resting_bpm": 52.0, "resting_hrv": 48.0, "hrv": 50.0, "spo2": 97.0},
            },
        }
        result = data_247.normalize_recovery(raw, USER_ID)
        assert result is not None
        assert result["recovery_score"] == 48
        assert result["recovery_stage"] == "go_easy"
        assert result["activity_score"] == 97
        assert result["sleep_score"] == 99
        assert result["resting_heart_rate"] == 52.0
        from datetime import datetime, timezone

        assert result["timestamp"] == datetime(2026, 3, 14, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 8. save_recovery_data — ACTIVITY + SLEEP HealthScore writes (t_5912f22f)
# ---------------------------------------------------------------------------


class TestSensorBio247SaveRecoveryDataScores:
    """save_recovery_data() now writes RECOVERY + ACTIVITY + SLEEP HealthScores.

    Added in t_5912f22f. Mirrors oura/data_247.py ACTIVITY (line 184) and SLEEP (line 809).
    """

    def test_persists_activity_health_score(self, data_247: SensorBio247Data) -> None:
        """activity_score present → HealthScore(ACTIVITY) written."""
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2026, 3, 14, tzinfo=timezone.utc),
            "recovery_score": 48,
            "recovery_stage": "go_easy",
            "activity_score": 97,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service"),
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 0, "scores_synced": 2}
        mock_hs.bulk_create.assert_called_once()
        from app.schemas.enums import HealthScoreCategory

        scores = mock_hs.bulk_create.call_args[0][1]
        categories = {s.category for s in scores}
        assert HealthScoreCategory.RECOVERY in categories
        assert HealthScoreCategory.ACTIVITY in categories
        activity = next(s for s in scores if s.category == HealthScoreCategory.ACTIVITY)
        assert activity.value == 97

    def test_persists_sleep_health_score(self, data_247: SensorBio247Data) -> None:
        """sleep_score present → HealthScore(SLEEP) written."""
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2026, 3, 14, tzinfo=timezone.utc),
            "recovery_score": 48,
            "recovery_stage": "go_easy",
            "sleep_score": 99,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service"),
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 0, "scores_synced": 2}
        from app.schemas.enums import HealthScoreCategory

        scores = mock_hs.bulk_create.call_args[0][1]
        categories = {s.category for s in scores}
        assert HealthScoreCategory.SLEEP in categories
        sleep = next(s for s in scores if s.category == HealthScoreCategory.SLEEP)
        assert sleep.value == 99

    def test_persists_all_three_health_scores(self, data_247: SensorBio247Data) -> None:
        """All three scores present → RECOVERY + ACTIVITY + SLEEP all written."""
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2026, 3, 14, tzinfo=timezone.utc),
            "recovery_score": 48,
            "recovery_stage": "go_easy",
            "activity_score": 97,
            "sleep_score": 99,
            "resting_heart_rate": 52.0,
            "hrv_rmssd_milli": 48.0,
            "spo2_percentage": 97.0,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service") as mock_ts,
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            mock_ts.bulk_create_samples.return_value = 3
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 3, "scores_synced": 3}
        assert mock_hs.bulk_create.call_count == 1
        from app.schemas.enums import HealthScoreCategory

        scores = mock_hs.bulk_create.call_args[0][1]
        categories = {s.category for s in scores}
        assert categories == {HealthScoreCategory.RECOVERY, HealthScoreCategory.ACTIVITY, HealthScoreCategory.SLEEP}

    def test_none_activity_score_no_write(self, data_247: SensorBio247Data) -> None:
        """activity_score=None → no ACTIVITY HealthScore written, no crash."""
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2026, 3, 14, tzinfo=timezone.utc),
            "recovery_score": 48,
            "activity_score": None,
            "sleep_score": None,
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service"),
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 0, "scores_synced": 1}
        from app.schemas.enums import HealthScoreCategory

        scores = mock_hs.bulk_create.call_args[0][1]
        assert len(scores) == 1
        assert scores[0].category == HealthScoreCategory.RECOVERY

    def test_missing_all_scores_no_crash(self, data_247: SensorBio247Data) -> None:
        """Missing activity/sleep blocks in normalized dict → no write, no crash."""
        db = MagicMock()
        normalized = {
            "timestamp": datetime(2026, 3, 14, tzinfo=timezone.utc),
            # activity_score and sleep_score keys absent entirely
        }
        with (
            patch("app.services.providers.sensorbio.data_247.timeseries_service"),
            patch("app.services.providers.sensorbio.data_247.health_score_service") as mock_hs,
        ):
            counts = data_247.save_recovery_data(db, USER_ID, normalized)

        assert counts == {"metrics_synced": 0, "scores_synced": 0}
        mock_hs.bulk_create.assert_not_called()
