"""Google Health API sleep sessions must carry ``type="sleep_session"``.

Regression test: ``EventRecordService`` only reaches the branch that *rewrites* an
existing sleep detail through ``find_adjacent_sleep_record``, which filters on
``EventRecord.type == "sleep_session"``. Every other provider sets the field, so a
Google session that was first published unclassified — Google's API returns a single
``sleeping`` block and fills in the stages moments later — could never be repaired: the
re-insert hits the ``(data_source_id, start_datetime, end_datetime)`` unique index,
returns the existing row, and the detail insert hits the primary key and returns the
stored detail untouched. The stages stayed lost for the life of the record.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.providers.google.health_api.sleep import GoogleHealthApiSleep


def _handler() -> GoogleHealthApiSleep:
    return GoogleHealthApiSleep(MagicMock(), MagicMock(), "https://health.googleapis.com")


def _point() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    interval = {
        "startTime": "2026-09-09T01:47:00Z",
        "endTime": "2026-09-09T07:59:00Z",
        "startUtcOffset": "7200s",
    }
    sleep = {
        "sleepStages": [
            {"stage": "DEEP", "interval": interval},
        ],
        "metadata": {"externalId": "sleep-1"},
    }
    point = {"name": "dataPoints/1", "dataSource": "derived:com.google.sleep.segment", "interval": interval}
    return point, sleep, interval


def test_sleep_record_is_typed_as_sleep_session() -> None:
    point, sleep, interval = _point()
    record, _detail = _handler()._normalize(
        point,
        sleep,
        interval,
        datetime(2026, 9, 9, 1, 47, tzinfo=timezone.utc),
        datetime(2026, 9, 9, 7, 59, tzinfo=timezone.utc),
        uuid4(),
    )

    assert record.category == "sleep"
    assert record.type == "sleep_session"
