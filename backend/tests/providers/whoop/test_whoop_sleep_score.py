from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.providers.whoop.data_247 import Whoop247Data


def test_sleep_score_is_recorded_at_the_wake_up() -> None:
    # A night that starts before midnight UTC belongs to the day the user wakes up
    data_247 = Whoop247Data(provider_name="whoop", api_base_url="https://api.prod.whoop.com", oauth=MagicMock())
    sleep = {
        "id": str(uuid4()),
        "start": "2026-10-27T23:55:00.000Z",
        "end": "2026-10-28T05:46:00.000Z",
        "timezone_offset": "+01:00",
        "nap": False,
        "score_state": "SCORED",
        "score": {"sleep_performance_percentage": 84},
    }

    normalized, score = data_247.normalize_sleep(sleep, uuid4())

    assert normalized["zone_offset"] == "+01:00"
    assert score is not None
    assert score.recorded_at == datetime(2026, 10, 28, 5, 46, tzinfo=timezone.utc)
    assert score.zone_offset == "+01:00"
