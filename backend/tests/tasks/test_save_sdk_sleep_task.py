from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry
from redis.exceptions import LockError

from app.integrations.celery.tasks import save_sdk_sleep_task as task
from app.schemas.providers.mobile_sdk import SyncRequest

REQUEST = SyncRequest.model_validate(
    {
        "provider": "apple",
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2026-01-01T08:00:00Z",
        "data": {
            "sleep": [
                {
                    "id": "s1",
                    "stage": "asleep_core",
                    "startDate": "2026-01-01T01:00:00Z",
                    "endDate": "2026-01-01T02:00:00Z",
                }
            ]
        },
    }
).model_dump_json()


def _run(retries: int, outcome: Exception | None) -> object:
    with (
        patch.object(task, "SessionLocal", MagicMock()),
        patch.object(task, "handle_sleep_data", side_effect=outcome) as handle,
        patch.object(task.save_sdk_sleep, "retry", side_effect=Retry()),
        patch.object(task.logger, "error") as error,
    ):
        task.save_sdk_sleep.push_request(retries=retries)
        try:
            return task.save_sdk_sleep.run(REQUEST, "user-1"), handle, error
        finally:
            task.save_sdk_sleep.pop_request()


def test_the_sleep_is_saved_once_the_lock_frees_up() -> None:
    result, handle, error = _run(0, None)

    assert result == {"status": "saved", "sleep_count": 1}
    handle.assert_called_once()
    error.assert_not_called()


def test_a_busy_lock_is_retried() -> None:
    with pytest.raises(Retry):
        _run(1, LockError("busy"))


def test_after_the_last_attempt_the_loss_is_reported() -> None:
    result, _, error = _run(task.save_sdk_sleep.max_retries, LockError("busy"))

    assert result == {"status": "dropped", "sleep_count": 1}
    assert error.call_args.kwargs["alert"] is True
