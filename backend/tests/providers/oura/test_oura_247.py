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
        result = data_247.normalize_sleep(sample_oura_sleep, user_id)

        assert result["user_id"] == user_id
        assert result["provider"] == "oura"
        assert result["oura_sleep_id"] == "sleep-abc123"
        assert result["duration_seconds"] == 28800
        assert result["efficiency_percent"] == 88.0

    def test_normalize_sleep_stages(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_oura_sleep, user_id)
        stages = result["stages"]

        assert stages["deep_seconds"] == 5400
        assert stages["light_seconds"] == 14400
        assert stages["rem_seconds"] == 7200
        assert stages["awake_seconds"] == 1800

    def test_normalize_sleep_timestamps(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_oura_sleep, user_id)

        assert result["start_time"] == "2024-01-15T23:00:00+00:00"
        assert result["end_time"] == "2024-01-15T07:00:00+00:00"

    def test_normalize_sleep_not_nap(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_oura_sleep, user_id)
        assert result["is_nap"] is False

    def test_normalize_sleep_nap_detection(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        raw = {
            "id": "sleep-nap",
            "bedtime_start": "2024-01-15T14:00:00+00:00",
            "bedtime_end": "2024-01-15T14:30:00+00:00",
            "type": "rest",
            "time_in_bed": 1800,
        }
        result = data_247.normalize_sleep(raw, user_id)
        assert result["is_nap"] is True

    def test_normalize_sleep_heart_rate(self, data_247: Oura247Data, sample_oura_sleep: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_oura_sleep, user_id)
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
        result = data_247.normalize_recovery(sample_oura_readiness, user_id)

        assert result["recovery_score"] == 82
        assert result["provider"] == "oura"
        assert result["user_id"] == user_id

    def test_normalize_readiness_temperature(self, data_247: Oura247Data, sample_oura_readiness: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_recovery(sample_oura_readiness, user_id)
        assert result["temperature_deviation"] == 0.15

    def test_normalize_readiness_timestamp(self, data_247: Oura247Data, sample_oura_readiness: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_recovery(sample_oura_readiness, user_id)
        assert result["timestamp"] is not None


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
        result = data_247.normalize_activity_samples(raw, user_id)

        assert len(result["steps"]) == 1
        assert result["steps"][0]["value"] == 8500
        assert len(result["energy"]) == 1
        assert result["energy"][0]["value"] == 350
        assert len(result["distance"]) == 1
        assert result["distance"][0]["value"] == 6500

    def test_normalize_activity_empty(self, data_247: Oura247Data) -> None:
        user_id = uuid4()
        result = data_247.normalize_activity_samples([], user_id)

        assert result["steps"] == []
        assert result["energy"] == []
        assert result["distance"] == []
