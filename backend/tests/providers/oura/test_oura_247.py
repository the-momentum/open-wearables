"""Tests for Oura247Data normalization."""

from uuid import uuid4

import pytest

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
                "equivalent_walking_distance": 6500,
                "timestamp": "2024-01-15T23:59:59+00:00",
            },
        ]
        samples, _ = data_247.normalize_activity_samples(raw, user_id)

        assert len(samples["steps"]) == 1
        assert samples["steps"][0]["value"] == 8500
        assert len(samples["energy"]) == 1
        assert samples["energy"][0]["value"] == 350
        assert len(samples["distance"]) == 1
        assert samples["distance"][0]["value"] == 6500

    def test_normalize_activity_empty(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        samples, _ = data_247.normalize_activity_samples([], user_id)

        assert samples["steps"] == []
        assert samples["energy"] == []
        assert samples["distance"] == []
