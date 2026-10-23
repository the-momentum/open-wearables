"""Tests for Whoop247Data sleep normalization."""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.model_crud.activities import EventRecordDetailCreate
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.strategy import WhoopStrategy


@pytest.fixture
def data_247() -> Whoop247Data:
    instance = WhoopStrategy().data_247
    assert isinstance(instance, Whoop247Data)
    return instance


def _raw_sleep(**overrides: Any) -> dict[str, Any]:
    raw = {
        "id": str(uuid4()),
        "cycle_id": 93845,
        "start": "2024-01-14T23:00:00.000Z",
        "end": "2024-01-15T07:00:00.000Z",
        "timezone_offset": "+00:00",
        "nap": False,
        "score_state": "SCORED",
        "score": {
            "stage_summary": {
                "total_in_bed_time_milli": 28_800_000,
                "total_awake_time_milli": 1_800_000,
                "total_light_sleep_time_milli": 14_400_000,
                "total_slow_wave_sleep_time_milli": 5_400_000,
                "total_rem_sleep_time_milli": 7_200_000,
            },
            "sleep_efficiency_percentage": 91.5,
        },
    }
    raw.update(overrides)
    return raw


def _saved_detail(data_247: Whoop247Data, raw: dict[str, Any]) -> EventRecordDetailCreate:
    normalized, _ = data_247.normalize_sleep(raw, uuid4())
    with patch("app.services.providers.whoop.data_247.event_record_service") as mock_event:
        data_247.save_sleep_data(MagicMock(), uuid4(), normalized)
    return mock_event.create_or_merge_sleep.call_args[0][3]


class TestWhoopSleepStages:
    def test_scored_sleep_saves_stage_minutes(self, data_247: Whoop247Data) -> None:
        detail = _saved_detail(data_247, _raw_sleep())

        assert detail.sleep_deep_minutes == 90
        assert detail.sleep_light_minutes == 240
        assert detail.sleep_rem_minutes == 120
        assert detail.sleep_awake_minutes == 30
        assert detail.sleep_total_duration_minutes == 450
        assert detail.sleep_time_in_bed_minutes == 480

    def test_scored_nap_keeps_reported_zero_stages(self, data_247: Whoop247Data) -> None:
        raw = _raw_sleep(nap=True)
        raw["score"]["stage_summary"].update(total_rem_sleep_time_milli=0, total_awake_time_milli=0)

        detail = _saved_detail(data_247, raw)

        assert detail.sleep_rem_minutes == 0
        assert detail.sleep_awake_minutes == 0

    def test_pending_score_leaves_stages_unreported(self, data_247: Whoop247Data) -> None:
        raw = _raw_sleep(score_state="PENDING_SCORE")
        del raw["score"]

        detail = _saved_detail(data_247, raw)

        assert detail.sleep_deep_minutes is None
        assert detail.sleep_light_minutes is None
        assert detail.sleep_rem_minutes is None
        assert detail.sleep_awake_minutes is None
        assert detail.sleep_total_duration_minutes is None
        # Time in bed still falls back to the session window
        assert detail.sleep_time_in_bed_minutes == 480
