"""Tests for Oura247Data normalization."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.constants.sleep import SleepStageType
from app.models import EventRecord, EventRecordAggregate, SeriesAggregate
from app.schemas.enums import SeriesType, get_series_type_id
from app.schemas.providers.oura.imports import OuraMetJSON
from app.services.providers.oura.coverage import ACTIVITY_SERIES
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.strategy import OuraStrategy


class TestOura247SleepNormalization:
    """Test sleep data normalization."""

    @pytest.fixture
    def data_247(self) -> Oura247Data:
        strategy = OuraStrategy()
        return strategy.data_247

    @pytest.fixture
    def sample_oura_sleep(self) -> dict:
        return {
            "id": "sleep-abc123",
            "average_breath": 15.5,
            "average_heart_rate": 55.0,
            "average_hrv": 45,
            "awake_time": 1800,
            "bedtime_end": "2024-01-15T07:00:00+00:00",
            "bedtime_start": "2024-01-15T23:00:00+00:00",
            "day": "2024-01-15",
            "deep_sleep_duration": 5400,
            "efficiency": 88,
            "latency": 300,
            "light_sleep_duration": 14400,
            "low_battery_alert": False,
            "lowest_heart_rate": 48,
            "period": 0,
            "rem_sleep_duration": 7200,
            "restless_periods": 5,
            "time_in_bed": 28800,
            "total_sleep_duration": 27000,
            "type": "long_sleep",
        }

    def test_normalize_sleep_basic_fields(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleeps([sample_oura_sleep], user_id)[0]

        assert result["user_id"] == user_id
        assert result["provider"] == "oura"
        assert result["oura_sleep_id"] == "sleep-abc123"
        assert result["duration_seconds"] == 28800
        assert result["efficiency_percent"] == 88.0

    def test_normalize_sleep_stages(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleeps([sample_oura_sleep], user_id)[0]
        stages = result["stages"]

        assert stages["deep_seconds"] == 5400
        assert stages["light_seconds"] == 14400
        assert stages["rem_seconds"] == 7200
        assert stages["awake_seconds"] == 1800

    def test_stage_timestamps_use_30_sec_hypnogram(self, data_247: Oura247Data) -> None:
        raw = {
            "id": "sleep-30s",
            "bedtime_start": "2024-01-15T23:00:00+00:00",
            "bedtime_end": "2024-01-16T07:00:00+00:00",
            "type": "long_sleep",
            "sleep_phase_30_sec": "1" * 4 + "3" * 2,  # 120s deep, 60s rem
        }
        stages = data_247.normalize_sleeps([raw], uuid4())[0]["stage_timestamps"]

        assert [s.stage for s in stages] == [SleepStageType.DEEP, SleepStageType.REM]
        assert stages[0].start_time == datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert stages[0].end_time == datetime(2024, 1, 15, 23, 2, tzinfo=timezone.utc)
        assert stages[1].end_time == datetime(2024, 1, 15, 23, 3, tzinfo=timezone.utc)

    def test_stage_timestamps_prefer_30_sec_over_5_min(self, data_247: Oura247Data) -> None:
        raw = {
            "id": "sleep-both",
            "bedtime_start": "2024-01-15T23:00:00+00:00",
            "bedtime_end": "2024-01-16T07:00:00+00:00",
            "type": "long_sleep",
            "sleep_phase_30_sec": "111",  # 90s deep — not expressible at 5-min resolution
            "sleep_phase_5_min": "2",
        }
        stages = data_247.normalize_sleeps([raw], uuid4())[0]["stage_timestamps"]

        assert len(stages) == 1
        assert stages[0].stage == SleepStageType.DEEP
        assert stages[0].end_time == datetime(2024, 1, 15, 23, 1, 30, tzinfo=timezone.utc)

    def test_stage_timestamps_fall_back_to_5_min(self, data_247: Oura247Data) -> None:
        raw = {
            "id": "sleep-5m",
            "bedtime_start": "2024-01-15T23:00:00+00:00",
            "bedtime_end": "2024-01-16T07:00:00+00:00",
            "type": "long_sleep",
            "sleep_phase_5_min": "14",  # 5min deep, 5min awake
        }
        stages = data_247.normalize_sleeps([raw], uuid4())[0]["stage_timestamps"]

        assert [s.stage for s in stages] == [SleepStageType.DEEP, SleepStageType.AWAKE]
        assert stages[0].end_time == datetime(2024, 1, 15, 23, 5, tzinfo=timezone.utc)
        assert stages[1].end_time == datetime(2024, 1, 15, 23, 10, tzinfo=timezone.utc)

    def test_normalize_sleep_timestamps(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleeps([sample_oura_sleep], user_id)[0]

        assert result["start_time"] == "2024-01-15T23:00:00+00:00"
        assert result["end_time"] == "2024-01-15T07:00:00+00:00"

    def test_normalize_sleep_not_nap(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleeps([sample_oura_sleep], user_id)[0]
        assert result["is_nap"] is False

    def test_normalize_sleep_nap_detection_sleep_type(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = {
            "id": "sleep-nap",
            "bedtime_start": "2024-01-15T14:00:00+00:00",
            "bedtime_end": "2024-01-15T14:30:00+00:00",
            "type": "sleep",
            "time_in_bed": 1800,
        }
        result = data_247.normalize_sleeps([raw], user_id)[0]
        assert result["is_nap"] is True

    def test_normalize_sleep_nap_detection_late_nap_type(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = {
            "id": "sleep-late-nap",
            "bedtime_start": "2024-01-15T23:30:00+00:00",
            "bedtime_end": "2024-01-16T00:30:00+00:00",
            "type": "late_nap",
            "time_in_bed": 3600,
        }
        result = data_247.normalize_sleeps([raw], user_id)[0]
        assert result["is_nap"] is True

    def test_normalize_sleep_skips_rest_type(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = {
            "id": "sleep-rest",
            "bedtime_start": "2024-01-15T14:00:00+00:00",
            "bedtime_end": "2024-01-15T14:30:00+00:00",
            "type": "rest",
            "time_in_bed": 1800,
        }
        result = data_247.normalize_sleeps([raw], user_id)
        assert result == []

    def test_normalize_sleep_skips_deleted_type(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = {
            "id": "sleep-deleted",
            "bedtime_start": "2024-01-15T14:00:00+00:00",
            "bedtime_end": "2024-01-15T14:30:00+00:00",
            "type": "deleted",
            "time_in_bed": 1800,
        }
        result = data_247.normalize_sleeps([raw], user_id)
        assert result == []

    def test_normalize_sleep_mixed_types_filters_correctly(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        items = [
            {
                "id": "s1",
                "bedtime_start": "2024-01-15T00:00:00+00:00",
                "bedtime_end": "2024-01-15T08:00:00+00:00",
                "type": "long_sleep",
                "time_in_bed": 28800,
            },
            {
                "id": "s2",
                "bedtime_start": "2024-01-15T14:00:00+00:00",
                "bedtime_end": "2024-01-15T14:30:00+00:00",
                "type": "sleep",
                "time_in_bed": 1800,
            },
            {
                "id": "s3",
                "bedtime_start": "2024-01-15T15:00:00+00:00",
                "bedtime_end": "2024-01-15T15:20:00+00:00",
                "type": "rest",
                "time_in_bed": 1200,
            },
            {
                "id": "s4",
                "bedtime_start": "2024-01-15T16:00:00+00:00",
                "bedtime_end": "2024-01-15T16:30:00+00:00",
                "type": "deleted",
                "time_in_bed": 1800,
            },
        ]
        result = data_247.normalize_sleeps(items, user_id)
        assert len(result) == 2
        assert result[0]["is_nap"] is False  # long_sleep
        assert result[1]["is_nap"] is True  # sleep

    @patch("app.services.providers.oura.data_247.event_record_service")
    def test_unreported_sleep_stages_are_saved_as_none(
        self, mock_event: MagicMock, data_247: Oura247Data, sample_oura_sleep: dict
    ) -> None:
        sample_oura_sleep.update(
            deep_sleep_duration=None, light_sleep_duration=None, rem_sleep_duration=None, awake_time=None
        )

        normalized = data_247.normalize_sleeps([sample_oura_sleep], uuid4())
        data_247.save_sleep_data(MagicMock(), uuid4(), normalized)

        detail = mock_event.create_or_merge_sleep.call_args[0][3]
        assert detail.sleep_deep_minutes is None
        assert detail.sleep_light_minutes is None
        assert detail.sleep_rem_minutes is None
        assert detail.sleep_awake_minutes is None
        assert detail.sleep_total_duration_minutes is None
        assert detail.sleep_time_in_bed_minutes == 480

    @patch("app.services.providers.oura.data_247.event_record_service")
    def test_reported_zero_sleep_stages_are_saved_as_zero(
        self, mock_event: MagicMock, data_247: Oura247Data, sample_oura_sleep: dict
    ) -> None:
        sample_oura_sleep.update(deep_sleep_duration=0, rem_sleep_duration=0)

        normalized = data_247.normalize_sleeps([sample_oura_sleep], uuid4())
        data_247.save_sleep_data(MagicMock(), uuid4(), normalized)

        detail = mock_event.create_or_merge_sleep.call_args[0][3]
        assert detail.sleep_deep_minutes == 0
        assert detail.sleep_rem_minutes == 0
        assert detail.sleep_light_minutes == 240
        assert detail.sleep_total_duration_minutes == 240

    def test_normalize_sleep_heart_rate(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleeps([sample_oura_sleep], user_id)[0]
        assert result["average_heart_rate"] == 55.0
        assert result["average_hrv"] == 45
        assert result["lowest_heart_rate"] == 48


class TestOura247ReadinessNormalization:
    """Test readiness (recovery) data normalization."""

    @pytest.fixture
    def data_247(self) -> Oura247Data:
        strategy = OuraStrategy()
        return strategy.data_247

    @pytest.fixture
    def sample_oura_readiness(self) -> dict:
        return {
            "id": "readiness-abc123",
            "day": "2024-01-15",
            "score": 82,
            "temperature_deviation": 0.15,
            "temperature_trend_deviation": 0.05,
            "timestamp": "2024-01-15T07:00:00+00:00",
        }

    def test_normalize_readiness_score(self, data_247: Oura247Data, sample_oura_readiness: dict) -> None:
        user_id = uuid4()
        recovery_metrics, health_scores = data_247.normalize_readiness([sample_oura_readiness], user_id)
        result = recovery_metrics[0]

        assert result["recovery_score"] == 82
        assert result["provider"] == "oura"
        assert result["user_id"] == user_id

    def test_normalize_readiness_temperature(self, data_247: Oura247Data, sample_oura_readiness: dict) -> None:
        user_id = uuid4()
        recovery_metrics, _ = data_247.normalize_readiness([sample_oura_readiness], user_id)
        assert recovery_metrics[0]["temperature_deviation"] == 0.15

    def test_normalize_readiness_timestamp(self, data_247: Oura247Data, sample_oura_readiness: dict) -> None:
        user_id = uuid4()
        recovery_metrics, _ = data_247.normalize_readiness([sample_oura_readiness], user_id)
        assert recovery_metrics[0]["timestamp"] is not None


class TestOura247ActivityNormalization:
    """Test activity data normalization."""

    @pytest.fixture
    def data_247(self) -> Oura247Data:
        strategy = OuraStrategy()
        return strategy.data_247

    def test_normalize_activity_samples(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = [
            {
                "id": "activity-1",
                "day": "2024-01-15",
                "steps": 8500,
                "active_calories": 350,
                "total_calories": 1800,
                "equivalent_walking_distance": 6500,
                "timestamp": "2024-01-15T23:59:59+00:00",
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, user_id)

        assert len(samples["steps"]) == 1
        assert samples["steps"][0]["value"] == 8500
        assert len(samples["energy"]) == 1
        assert samples["energy"][0]["value"] == 350
        assert samples["basal_energy"][0]["value"] == 1450
        assert len(samples["distance"]) == 1
        assert samples["distance"][0]["value"] == 6500

    def test_normalize_activity_empty(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        samples, _ = data_247.normalize_activity_samples([], user_id)

        assert samples["steps"] == []
        assert samples["energy"] == []
        assert samples["distance"] == []

    def test_normalize_activity_samples_includes_met(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = [
            {
                "id": "activity-met",
                "day": "2024-01-15",
                "timestamp": "2024-01-15T00:00:00+00:00",
                "met": {
                    "interval": 60,
                    "items": [1.0, 1.2, None, 1.5],
                    "timestamp": "2024-01-15T00:00:00+00:00",
                },
                "class_5_min": "2",
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, user_id)

        assert len(samples["met"]) == 3
        assert [s["value"] for s in samples["met"]] == [1.0, 1.2, 1.5]
        assert {s["window_seconds"] for s in samples["met"]} == {60}

    def test_normalize_activity_samples_met_absent(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = [{"id": "activity-no-met", "day": "2024-01-15", "timestamp": "2024-01-15T00:00:00+00:00"}]
        samples, _ = data_247.normalize_activity_samples(raw, user_id)

        assert samples["met"] == []

    def test_normalize_activity_samples_exercise_time(self, data_247: Oura247Data) -> None:
        # High + medium is exercise time; low counts only toward active time.
        raw = [
            {
                "id": "activity-1",
                "day": "2024-01-15",
                "timestamp": "2024-01-15T00:00:00+00:00",
                "high_activity_time": 1830,
                "medium_activity_time": 1230,
                "low_activity_time": 3600,
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, uuid4())

        assert [s["value"] for s in samples["exercise_time"]] == [51]
        assert [s["value"] for s in samples["active_time"]] == [111]

    def test_normalize_activity_samples_exercise_time_from_one_field(self, data_247: Oura247Data) -> None:
        raw = [
            {
                "id": "activity-1",
                "day": "2024-01-15",
                "timestamp": "2024-01-15T00:00:00+00:00",
                "medium_activity_time": 610,
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, uuid4())

        assert [s["value"] for s in samples["exercise_time"]] == [10]

    def test_normalize_activity_samples_exercise_time_absent(self, data_247: Oura247Data) -> None:
        raw = [
            {
                "id": "activity-1",
                "day": "2024-01-15",
                "timestamp": "2024-01-15T00:00:00+00:00",
                "low_activity_time": 3600,
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, uuid4())

        assert samples["exercise_time"] == []

    def test_exercise_time_maps_to_exercise_time_series(self) -> None:
        assert ACTIVITY_SERIES["exercise_time"] == SeriesType.exercise_time


class TestOura247MetSeriesExpansion:
    """Test expansion of the intraday MET series embedded in daily activity records."""

    @pytest.fixture
    def data_247(self) -> Oura247Data:
        strategy = OuraStrategy()
        return strategy.data_247

    def test_expand_met_series_basic(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0, 1.1, 1.2], timestamp="2024-01-15T00:00:00+00:00")
        samples = data_247._expand_met_series(met, "2")

        assert [s["value"] for s in samples] == [1.0, 1.1, 1.2]
        assert samples[0]["recorded_at"] == datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert samples[1]["recorded_at"] == datetime(2024, 1, 15, 0, 1, 0, tzinfo=timezone.utc)
        assert samples[2]["recorded_at"] == datetime(2024, 1, 15, 0, 2, 0, tzinfo=timezone.utc)

    def test_expand_met_series_skips_null_items(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0, None, 1.2], timestamp="2024-01-15T00:00:00+00:00")
        samples = data_247._expand_met_series(met, "2")

        # A null (unworn/unmeasured) sample must be dropped, never coerced to 0.0.
        assert [s["value"] for s in samples] == [1.0, 1.2]

    def test_expand_met_series_skips_not_worn_sentinel(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0, 0.1, 1.2], timestamp="2024-01-15T00:00:00+00:00")
        samples = data_247._expand_met_series(met, "2")

        assert [s["value"] for s in samples] == [1.0, 1.2]

    def test_expand_met_series_all_null(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[None, None], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_missing_met(self, data_247: Oura247Data) -> None:
        assert data_247._expand_met_series(None, "2") == []

    def test_expand_met_series_empty_items(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_missing_interval_is_dropped(self, data_247: Oura247Data) -> None:
        # Oura's schema documents `interval` as a plain float, not a fixed 60s cadence —
        # a missing value must not be guessed.
        met = OuraMetJSON(interval=None, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_zero_interval_is_dropped(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=0, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_negative_interval_is_dropped(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=-60, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_unrepresentable_interval_returns_empty(self, data_247: Oura247Data) -> None:
        # A finite but huge interval overflows `timedelta` once multiplied by the item
        # index, instead of raising and failing the whole activity import.
        met = OuraMetJSON(interval=1e20, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00+00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_unparseable_timestamp_is_dropped(self, data_247: Oura247Data) -> None:
        # No fallback to the daily activity's own timestamp — it can anchor the whole
        # series to the wrong point in the day (mirrors the sleep HR/HRV interval handling).
        met = OuraMetJSON(interval=60, items=[1.0], timestamp="not-a-timestamp")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_missing_timestamp_is_dropped(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0], timestamp=None)
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_offset_less_timestamp_is_dropped(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00")
        assert data_247._expand_met_series(met, "2") == []

    def test_expand_met_series_full_day(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0] * 1440, timestamp="2024-01-15T00:00:00+00:00")
        samples = data_247._expand_met_series(met, "2" * 288)

        assert len(samples) == 1440
        assert samples[-1]["recorded_at"] == datetime(2024, 1, 15, 23, 59, 0, tzinfo=timezone.utc)

    def test_expand_met_series_carries_zone_offset(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0], timestamp="2024-01-15T00:00:00+02:00")
        samples = data_247._expand_met_series(met, "2")

        assert samples[0]["zone_offset"] == "+02:00"

    def test_met_maps_to_physical_effort(self) -> None:
        # Oura's per-minute MET is physical_effort; a workout's average MET is that series' session value.
        assert ACTIVITY_SERIES["met"] == SeriesType.physical_effort

    def test_expand_met_series_drops_unmeasured_tail_using_class_5_min_length(self, data_247: Oura247Data) -> None:
        # Reproduces real Oura behavior: `met.items` is pre-allocated for the full
        items = [1.2] * 10 + [0.9] * 1430
        class_5_min = "22"  # only the first 10 minutes (2 * 5 min) have been measured
        met = OuraMetJSON(interval=60, items=items, timestamp="2024-01-15T04:00:00+00:00")

        samples = data_247._expand_met_series(met, class_5_min)

        assert len(samples) == 10
        assert all(s["value"] == 1.2 for s in samples)

    def test_expand_met_series_keeps_genuine_low_value_within_measured_window(self, data_247: Oura247Data) -> None:
        items = [0.9] * 5
        met = OuraMetJSON(interval=60, items=items, timestamp="2024-01-15T04:00:00+00:00")

        samples = data_247._expand_met_series(met, "1")

        assert [s["value"] for s in samples] == [0.9] * 5

    def test_expand_met_series_drops_not_worn_values_regardless_of_class_5_min_content(
        self, data_247: Oura247Data
    ) -> None:
        items = [1.2, 1.2, 1.2, 1.2, 1.2, 0.1, 0.1, 0.1, 0.1, 0.1]
        class_5_min = "22"
        met = OuraMetJSON(interval=60, items=items, timestamp="2024-01-15T04:00:00+00:00")

        samples = data_247._expand_met_series(met, class_5_min)

        assert len(samples) == 5
        assert all(s["value"] == 1.2 for s in samples)

    def test_expand_met_series_without_class_5_min_is_dropped(self, data_247: Oura247Data) -> None:
        met = OuraMetJSON(interval=60, items=[1.0, 1.1], timestamp="2024-01-15T00:00:00+00:00")

        assert data_247._expand_met_series(met, None) == []


def test_save_activity_data_mirrors_day_totals_but_not_met(db: Session) -> None:
    from tests.factories import UserFactory

    data_247 = OuraStrategy().data_247
    assert isinstance(data_247, Oura247Data)
    user = UserFactory()
    raw = [
        {
            "id": "activity-1",
            "day": "2024-01-15",
            "timestamp": "2024-01-15T04:00:00-08:00",
            "steps": 9000,
            "met": {"interval": 60, "items": [1.0, 1.2], "timestamp": "2024-01-15T04:00:00-08:00"},
            "class_5_min": "2",
        }
    ]

    data_247.save_activity_data(db, user.id, data_247.normalize_activity_samples(raw, user.id))

    # Oura's day starts at 4 AM, but the day value belongs to the whole local date.
    assert [(a.series_type_definition_id, a.period_start, a.zone_offset, a.sum) for a in db.query(SeriesAggregate)] == [
        (get_series_type_id(SeriesType.steps), datetime(2024, 1, 15, 8, tzinfo=timezone.utc), "-08:00", Decimal("9000"))
    ]


def test_nightly_scalars_point_at_the_stored_sleep(db: Session) -> None:
    from tests.factories import UserFactory

    data_247 = OuraStrategy().data_247
    assert isinstance(data_247, Oura247Data)
    user = UserFactory()
    raw = [
        {
            "id": "oura-sleep-1",
            "day": "2024-01-15",
            "type": "long_sleep",
            "bedtime_start": "2024-01-14T23:10:00+01:00",
            "bedtime_end": "2024-01-15T07:05:00+01:00",
            "time_in_bed": 28500,
            "deep_sleep_duration": 5400,
            "light_sleep_duration": 14400,
            "rem_sleep_duration": 6000,
            "awake_time": 2700,
            "average_breath": 14.5,
            "lowest_heart_rate": 48,
        }
    ]

    data_247.save_sleep_data(db, user.id, data_247.normalize_sleeps(raw, user.id))

    sleep = db.query(EventRecord).filter(EventRecord.category == "sleep").one()
    rows = {row.series_type_definition_id: row for row in db.query(EventRecordAggregate)}
    assert {row.record_id for row in rows.values()} == {sleep.id}
    assert rows[get_series_type_id(SeriesType.respiratory_rate)].avg == Decimal("14.5")
    assert rows[get_series_type_id(SeriesType.resting_heart_rate)].avg == Decimal("48")
