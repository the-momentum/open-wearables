"""Tests for PolarData247Template sleep (Sleep Plus Stages) normalization."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from app.constants.sleep import SleepStageType
from app.services.providers.polar.data_247 import PolarData247Template
from app.services.providers.polar.strategy import PolarStrategy


@pytest.fixture
def data_247() -> PolarData247Template:
    return PolarStrategy().data_247


@pytest.fixture
def sample_polar_night() -> dict[str, Any]:
    """Single night from /v3/users/sleep — full docs example."""
    return {
        "polar_user": "https://www.polaraccesslink/v3/users/1",
        "date": "2020-01-01",
        "sleep_start_time": "2020-01-01T00:39:07+03:00",
        "sleep_end_time": "2020-01-01T09:19:37+03:00",
        "device_id": "1111AAAA",
        "continuity": 2.1,
        "continuity_class": 2,
        "light_sleep": 1000,
        "deep_sleep": 1000,
        "rem_sleep": 1000,
        "unrecognized_sleep_stage": 1000,
        "sleep_score": 80,
        "total_interruption_duration": 1000,
        "sleep_charge": 3,
        "sleep_goal": 28800,
        "sleep_rating": 3,
        "short_interruption_duration": 500,
        "long_interruption_duration": 300,
        "sleep_cycles": 6,
        "group_duration_score": 100,
        "group_solidity_score": 75,
        "group_regeneration_score": 54.2,
        "hypnogram": {"00:39": 2, "00:50": 3, "01:23": 6},
        "heart_rate_samples": {"00:41": 76, "00:46": 77, "00:51": 76},
    }


class TestPolarSleepNormalization:
    def test_basic_fields(self, data_247: PolarData247Template, sample_polar_night: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)

        assert result["provider"] == "polar"
        assert result["user_id"] == user_id
        assert result["external_id"] == "2020-01-01"
        assert result["polar_sleep_date"] == "2020-01-01"
        # 00:39:07 → 09:19:37 same tz = 8h 40m 30s = 31230s
        assert result["duration_seconds"] == 31230

    def test_stage_summary_minutes(self, data_247: PolarData247Template, sample_polar_night: dict) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)
        stages = result["stages"]

        # Polar reports durations in seconds; awake_seconds derives from total_interruption_duration
        assert stages["deep_seconds"] == 1000
        assert stages["light_seconds"] == 1000
        assert stages["rem_seconds"] == 1000
        assert stages["awake_seconds"] == 1000

    def test_hypnogram_to_stage_intervals(
        self, data_247: PolarData247Template, sample_polar_night: dict
    ) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)
        intervals = result["stage_timestamps"]

        # Three transitions → three intervals, last one ends at sleep_end_time
        assert len(intervals) == 3

        # First interval: 00:39 → 00:50, code 2 → LIGHT
        assert intervals[0].stage == SleepStageType.LIGHT
        # All three transitions on 2020-01-01 (same day as sleep_start_time)
        assert intervals[0].start_time.isoformat().startswith("2020-01-01T00:39")
        assert intervals[0].end_time.isoformat().startswith("2020-01-01T00:50")

        # Second interval: 00:50 → 01:23, code 3 → LIGHT
        assert intervals[1].stage == SleepStageType.LIGHT
        assert intervals[1].start_time.isoformat().startswith("2020-01-01T00:50")
        assert intervals[1].end_time.isoformat().startswith("2020-01-01T01:23")

        # Third interval: 01:23 → sleep_end_time, code 6 is out-of-range → UNKNOWN
        assert intervals[2].stage == SleepStageType.UNKNOWN
        assert intervals[2].start_time.isoformat().startswith("2020-01-01T01:23")
        # sleep_end_time is 09:19 same day
        assert intervals[2].end_time.isoformat().startswith("2020-01-01T09:19")

    def test_efficiency_from_sleep_score(
        self, data_247: PolarData247Template, sample_polar_night: dict
    ) -> None:
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)
        assert result["efficiency_percent"] == 80.0

    def test_missing_hypnogram_empty_intervals(
        self, data_247: PolarData247Template, sample_polar_night: dict
    ) -> None:
        sample_polar_night.pop("hypnogram")
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)
        # Summary durations still present
        assert result["stages"]["deep_seconds"] == 1000
        assert result["stage_timestamps"] == []

    def test_malformed_missing_start_returns_empty(
        self, data_247: PolarData247Template, sample_polar_night: dict
    ) -> None:
        sample_polar_night.pop("sleep_start_time")
        user_id = uuid4()
        result = data_247.normalize_sleep(sample_polar_night, user_id)
        assert result == {}


class TestPolarSleepFetch:
    def test_get_sleep_data_unwraps_nights(self, data_247: PolarData247Template, monkeypatch) -> None:
        """`get_sleep_data` must return the `nights` list from the wrapped response."""
        captured_endpoints: list[str] = []

        def fake_make_api_request(
            db, user_id, endpoint, params=None  # noqa: ANN001
        ) -> dict:
            captured_endpoints.append(endpoint)
            return {"nights": [{"date": "2020-01-01"}, {"date": "2020-01-02"}]}

        monkeypatch.setattr(data_247, "_make_api_request", fake_make_api_request)

        result = data_247.get_sleep_data(
            db=None,  # type: ignore[arg-type]
            user_id=uuid4(),
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2020, 1, 2, tzinfo=timezone.utc),
        )

        assert captured_endpoints == ["/v3/users/sleep"]
        assert [n["date"] for n in result] == ["2020-01-01", "2020-01-02"]

    def test_get_sleep_data_handles_non_dict_gracefully(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        """204 / None / malformed upstream should yield an empty list, not raise."""

        def fake_make_api_request(
            db, user_id, endpoint, params=None  # noqa: ANN001
        ) -> None:
            return None

        monkeypatch.setattr(data_247, "_make_api_request", fake_make_api_request)

        result = data_247.get_sleep_data(
            db=None,  # type: ignore[arg-type]
            user_id=uuid4(),
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2020, 1, 2, tzinfo=timezone.utc),
        )
        assert result == []
