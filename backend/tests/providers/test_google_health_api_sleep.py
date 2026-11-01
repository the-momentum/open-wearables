from unittest.mock import MagicMock
from uuid import uuid4

from app.services.providers.google_health.sleep import GoogleHealthApiSleep


def test_invalid_sleep_efficiency_is_not_stored() -> None:
    handler = GoogleHealthApiSleep(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="")

    detail = handler._build_detail(
        uuid4(),
        {
            "summary": {
                "minutesInSleepPeriod": 250,
                "minutesAsleep": 344,
            }
        },
        {},
    )

    assert detail.sleep_efficiency_score is None


def test_valid_sleep_efficiency_is_stored() -> None:
    handler = GoogleHealthApiSleep(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="")

    detail = handler._build_detail(
        uuid4(),
        {
            "summary": {
                "minutesInSleepPeriod": 480,
                "minutesAsleep": 420,
            }
        },
        {},
    )

    assert detail.sleep_efficiency_score is not None
    assert float(detail.sleep_efficiency_score) == 87.5
