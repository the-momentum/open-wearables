"""Tests for Polar247Data normalization."""

from uuid import uuid4

import pytest

from app.schemas.enums import HealthScoreCategory, SeriesType
from app.services.providers.polar.data_247 import Polar247Data
from app.services.providers.polar.strategy import PolarStrategy


@pytest.fixture
def data_247() -> Polar247Data:
    return PolarStrategy().data_247


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------


class TestPolar247SleepNormalization:
    @pytest.fixture
    def sample_sleep(self) -> dict:
        return {
            "polar_user": "https://www.polaraccesslink.com/v3/users/123",
            "date": "2024-01-15",
            "sleep_start_time": "2024-01-14T23:00:00+02:00",
            "sleep_end_time": "2024-01-15T07:00:00+02:00",
            "device_id": "Polar Vantage V3",
            "light_sleep": 14400,
            "deep_sleep": 5400,
            "rem_sleep": 7200,
            "total_interruption_duration": 1800,
            "sleep_score": 82,
            "group_duration_score": 4.2,
            "group_solidity_score": 3.8,
            "continuity": 3.1,
            "long_interruption_duration": 300,
            "hypnogram": {"23:00": 0, "23:30": 2, "00:30": 4, "02:30": 1, "04:00": 2},
            "heart_rate_samples": {"23:30": 58, "00:00": 54, "00:30": 52},
        }

    def test_basic_fields(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        record, detail, score, hr = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert record.user_id == user_id
        assert record.provider == "polar"
        assert record.category == "sleep"
        assert record.device_model is None

    def test_timestamps(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        record, _, _, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert record.start_datetime.isoformat() == "2024-01-14T23:00:00+02:00"
        assert record.end_datetime.isoformat() == "2024-01-15T07:00:00+02:00"
        assert record.duration_seconds == 8 * 3600

    def test_sleep_stage_minutes(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        _, detail, _, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert detail.sleep_deep_minutes == 90
        assert detail.sleep_light_minutes == 240
        assert detail.sleep_rem_minutes == 120
        assert detail.sleep_awake_minutes == 30
        assert detail.sleep_time_in_bed_minutes == 8 * 60

    def test_sleep_total_duration_excludes_awake(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        _, detail, _, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]

        # total = (light + deep + rem) / 60
        assert detail.sleep_total_duration_minutes == (14400 + 5400 + 7200) // 60

    def test_sleep_score(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        _, _, score, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert score is not None
        assert score.value == 82
        assert score.category == HealthScoreCategory.SLEEP
        assert score.provider.value == "polar"
        assert "sleep_time" in score.components
        assert "actual_sleep" in score.components

    def test_no_score_when_missing(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        sample_sleep.pop("sleep_score")
        user_id = uuid4()
        _, _, score, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]
        assert score is None

    def test_hr_timeseries(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        _, _, _, hr_samples = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert len(hr_samples) == 3
        assert all(s.series_type == SeriesType.heart_rate for s in hr_samples)
        assert all(s.user_id == user_id for s in hr_samples)
        bpm_values = {s.value for s in hr_samples}
        assert bpm_values == {58, 54, 52}

    def test_hypnogram_produces_stages(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        user_id = uuid4()
        _, detail, _, _ = data_247.normalize_sleep([sample_sleep], user_id)[0]

        assert detail.sleep_stages is not None
        assert len(detail.sleep_stages) > 0
        stage_types = {s.stage.value for s in detail.sleep_stages}
        assert "awake" in stage_types or "light" in stage_types or "deep" in stage_types

    def test_missing_start_time_skipped(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        sample_sleep.pop("sleep_start_time")
        user_id = uuid4()
        assert data_247.normalize_sleep([sample_sleep], user_id) == []

    def test_missing_end_time_skipped(self, data_247: Polar247Data, sample_sleep: dict) -> None:
        sample_sleep.pop("sleep_end_time")
        user_id = uuid4()
        assert data_247.normalize_sleep([sample_sleep], user_id) == []

    def test_empty_input(self, data_247: Polar247Data) -> None:
        assert data_247.normalize_sleep([], uuid4()) == []


# ---------------------------------------------------------------------------
# Daily Activity
# ---------------------------------------------------------------------------


class TestPolar247DailyActivityNormalization:
    @pytest.fixture
    def sample_activity(self) -> dict:
        return {
            "polar_user": "https://www.polaraccesslink.com/v3/users/123",
            "date": "2024-01-15",
            "start_time": "2024-01-15T00:00:00",
            "steps": 9500,
            "active_calories": 420,
            "distance_from_steps": 7200,
        }

    def test_all_three_series_types(self, data_247: Polar247Data, sample_activity: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_daily_activity([sample_activity], user_id)

        types = {s.series_type for s in samples}
        assert SeriesType.steps in types
        assert SeriesType.energy in types
        assert SeriesType.distance_walking_running in types

    def test_steps_value(self, data_247: Polar247Data, sample_activity: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_daily_activity([sample_activity], user_id)
        step_sample = next(s for s in samples if s.series_type == SeriesType.steps)
        assert step_sample.value == 9500
        assert step_sample.user_id == user_id

    def test_energy_value(self, data_247: Polar247Data, sample_activity: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_daily_activity([sample_activity], user_id)
        energy_sample = next(s for s in samples if s.series_type == SeriesType.energy)
        assert energy_sample.value == 420

    def test_distance_value(self, data_247: Polar247Data, sample_activity: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_daily_activity([sample_activity], user_id)
        dist_sample = next(s for s in samples if s.series_type == SeriesType.distance_walking_running)
        assert dist_sample.value == 7200

    def test_missing_steps_no_sample(self, data_247: Polar247Data, sample_activity: dict) -> None:
        sample_activity.pop("steps")
        user_id = uuid4()
        samples = data_247.normalize_daily_activity([sample_activity], user_id)
        assert not any(s.series_type == SeriesType.steps for s in samples)

    def test_missing_start_time_skipped(self, data_247: Polar247Data, sample_activity: dict) -> None:
        sample_activity.pop("start_time")
        user_id = uuid4()
        assert data_247.normalize_daily_activity([sample_activity], user_id) == []

    def test_empty_input(self, data_247: Polar247Data) -> None:
        assert data_247.normalize_daily_activity([], uuid4()) == []


# ---------------------------------------------------------------------------
# Continuous Heart Rate
# ---------------------------------------------------------------------------


class TestPolar247ContinuousHRNormalization:
    @pytest.fixture
    def sample_chr(self) -> dict:
        return {
            "polar_user": "https://www.polaraccesslink.com/v3/users/123",
            "date": "2024-01-15T00:00:00",
            "heart_rate_samples": [
                {"heart_rate": 62, "sample_time": "08:00"},
                {"heart_rate": 65, "sample_time": "08:05"},
                {"heart_rate": 60, "sample_time": "08:10"},
            ],
        }

    def test_produces_hr_timeseries(self, data_247: Polar247Data, sample_chr: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_continuous_hr([sample_chr], user_id)

        assert len(samples) == 3
        assert all(s.series_type == SeriesType.heart_rate for s in samples)
        assert all(s.user_id == user_id for s in samples)

    def test_bpm_values(self, data_247: Polar247Data, sample_chr: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_continuous_hr([sample_chr], user_id)
        bpm_values = [s.value for s in samples]
        assert bpm_values == [62, 65, 60]

    def test_timestamps_use_date_as_anchor(self, data_247: Polar247Data, sample_chr: dict) -> None:
        user_id = uuid4()
        samples = data_247.normalize_continuous_hr([sample_chr], user_id)
        assert samples[0].recorded_at.date().isoformat() == "2024-01-15"
        assert samples[0].recorded_at.hour == 8
        assert samples[0].recorded_at.minute == 0

    def test_missing_samples_skipped(self, data_247: Polar247Data, sample_chr: dict) -> None:
        sample_chr["heart_rate_samples"] = []
        user_id = uuid4()
        assert data_247.normalize_continuous_hr([sample_chr], user_id) == []

    def test_empty_input(self, data_247: Polar247Data) -> None:
        assert data_247.normalize_continuous_hr([], uuid4()) == []


# ---------------------------------------------------------------------------
# Cardio Load
# ---------------------------------------------------------------------------


class TestPolar247CardioLoadNormalization:
    @pytest.fixture
    def sample_cardio_load(self) -> dict:
        return {
            "date": "2024-01-15",
            "cardio_load_status": "LOAD_STATUS_MAINTAINING",
            "cardio_load": 42.5,
            "strain": 38.0,
            "tolerance": 55.0,
            "cardio_load_ratio": 0.77,
            "cardio_load_level": {
                "very_low": 0.05,
                "low": 0.15,
                "medium": 0.60,
                "high": 0.18,
                "very-high": 0.02,
            },
        }

    def test_produces_strain_score(self, data_247: Polar247Data, sample_cardio_load: dict) -> None:
        user_id = uuid4()
        scores = data_247.normalize_cardio_load([sample_cardio_load], user_id)

        assert len(scores) == 1
        score = scores[0]
        assert score.category == HealthScoreCategory.STRAIN
        assert score.value == 42.5
        assert score.provider.value == "polar"
        assert score.user_id == user_id

    def test_components(self, data_247: Polar247Data, sample_cardio_load: dict) -> None:
        user_id = uuid4()
        score = data_247.normalize_cardio_load([sample_cardio_load], user_id)[0]

        assert "strain" in score.components
        assert score.components["strain"].value == 38.0
        assert "tolerance" in score.components
        assert "cardio_load_ratio" in score.components
        assert "level_medium" in score.components

    def test_not_available_status_skipped(self, data_247: Polar247Data, sample_cardio_load: dict) -> None:
        sample_cardio_load["cardio_load_status"] = "LOAD_STATUS_NOT_AVAILABLE"
        user_id = uuid4()
        assert data_247.normalize_cardio_load([sample_cardio_load], user_id) == []

    def test_missing_cardio_load_value_skipped(self, data_247: Polar247Data, sample_cardio_load: dict) -> None:
        sample_cardio_load.pop("cardio_load")
        user_id = uuid4()
        assert data_247.normalize_cardio_load([sample_cardio_load], user_id) == []

    def test_empty_input(self, data_247: Polar247Data) -> None:
        assert data_247.normalize_cardio_load([], uuid4()) == []


# ---------------------------------------------------------------------------
# Nightly Recharge
# ---------------------------------------------------------------------------


class TestPolar247NightlyRechargeNormalization:
    @pytest.fixture
    def sample_recharge(self) -> dict:
        return {
            "date": "2024-01-15",
            "heart_rate_avg": 52,
            "beat_to_beat_avg": 1154,
            "heart_rate_variability_avg": 48,
            "breathing_rate_avg": 14.5,
            "nightly_recharge_status": 5,
            "ans_charge": 1.2,
            "ans_charge_status": 3,
        }

    def test_produces_recovery_score(self, data_247: Polar247Data, sample_recharge: dict) -> None:
        user_id = uuid4()
        scores = data_247.normalize_nightly_recharge([sample_recharge], user_id)

        assert len(scores) == 1
        score = scores[0]
        assert score.category == HealthScoreCategory.RECOVERY
        assert score.value == 5
        assert score.qualifier == "good"
        assert score.user_id == user_id

    def test_components_include_hrv(self, data_247: Polar247Data, sample_recharge: dict) -> None:
        user_id = uuid4()
        score = data_247.normalize_nightly_recharge([sample_recharge], user_id)[0]

        assert "heart_rate_variability_avg" in score.components
        assert score.components["heart_rate_variability_avg"].value == 48
        assert "ans_charge" in score.components
        assert "heart_rate_avg" in score.components

    def test_ans_charge_status_qualifier(self, data_247: Polar247Data, sample_recharge: dict) -> None:
        user_id = uuid4()
        score = data_247.normalize_nightly_recharge([sample_recharge], user_id)[0]

        assert "ans_charge_status" in score.components
        assert score.components["ans_charge_status"].qualifier == "usual"

    def test_status_labels(self, data_247: Polar247Data, sample_recharge: dict) -> None:
        user_id = uuid4()
        for status, label in [(1, "very poor"), (2, "poor"), (3, "compromised"), (4, "ok"), (6, "very good")]:
            sample_recharge["nightly_recharge_status"] = status
            score = data_247.normalize_nightly_recharge([sample_recharge], user_id)[0]
            assert score.qualifier == label

    def test_missing_status_skipped(self, data_247: Polar247Data, sample_recharge: dict) -> None:
        sample_recharge.pop("nightly_recharge_status")
        user_id = uuid4()
        assert data_247.normalize_nightly_recharge([sample_recharge], user_id) == []

    def test_empty_input(self, data_247: Polar247Data) -> None:
        assert data_247.normalize_nightly_recharge([], uuid4()) == []


# ---------------------------------------------------------------------------
# Hypnogram parsing
# ---------------------------------------------------------------------------


class TestPolar247HypnogramParsing:
    def test_consecutive_same_stage_grouped(self, data_247: Polar247Data) -> None:
        from datetime import datetime, timezone

        start = datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 16, 7, 0, tzinfo=timezone.utc)
        # Two consecutive light (2) entries then deep (4)
        hypnogram = {"23:00": 2, "23:30": 2, "00:30": 4}
        stages = data_247._parse_hypnogram(hypnogram, start, end)

        # First two 2s should merge into one light stage
        light_stages = [s for s in stages if s.stage.value == "light"]
        assert len(light_stages) == 1

    def test_midnight_crossover(self, data_247: Polar247Data) -> None:
        from datetime import datetime, timezone

        start = datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 16, 7, 0, tzinfo=timezone.utc)
        hypnogram = {"23:00": 2, "00:00": 4}
        stages = data_247._parse_hypnogram(hypnogram, start, end)

        assert len(stages) == 2
        # The 00:00 stage should be on Jan 16, not Jan 15
        deep_stage = next(s for s in stages if s.stage.value == "deep")
        assert deep_stage.start_time.day == 16

    def test_empty_hypnogram(self, data_247: Polar247Data) -> None:
        from datetime import datetime, timezone

        start = datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 16, 7, 0, tzinfo=timezone.utc)
        assert data_247._parse_hypnogram({}, start, end) == []
