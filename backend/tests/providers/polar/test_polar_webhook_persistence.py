"""Polar webhook writes must survive the Celery session and accept a single-day response.

The webhook task closes its session without committing, so anything the handler
writes is discarded unless the handler commits. The continuous heart rate webhook
also fetches one day (``{polar_user, date, heart_rate_samples}``), while the
``heart_rates`` wrapper only exists on the date-range endpoint used by polling.
"""

from typing import Any
from unittest.mock import patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataSource
from app.schemas.providers.polar import PolarWebhookEventType
from app.services.providers.polar.data_247 import Polar247Data
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.polar.webhook_handler import PolarWebhookHandler
from tests.factories import UserConnectionFactory, UserFactory

POLAR_USER_ID = "475"
ENDPOINT = "/v3/users/continuous-heart-rate/2026-09-10"

# Response of GET /v3/users/continuous-heart-rate/{date}: a single day, no wrapper.
DAY_RESPONSE: dict[str, Any] = {
    "polar_user": "https://www.polaraccesslink/v3/users/475",
    "date": "2026-09-10",
    "heart_rate_samples": [
        {"heart_rate": 59, "sample_time": "04:34:00"},
        {"heart_rate": 62, "sample_time": "04:40:00"},
    ],
}


def _polar_samples(db: Session, user_id: Any) -> list[DataPointSeries]:
    return (
        db.query(DataPointSeries)
        .join(DataSource, DataSource.id == DataPointSeries.data_source_id)
        .filter(DataSource.user_id == user_id, DataSource.provider == "polar")
        .all()
    )


def test_continuous_hr_webhook_saves_the_single_day_response(db: Session) -> None:
    user = UserFactory()
    data_247 = PolarStrategy().data_247
    assert isinstance(data_247, Polar247Data)

    with patch.object(Polar247Data, "_make_api_request", return_value=DAY_RESPONSE):
        saved = data_247.fetch_and_save_from_webhook(
            db, UUID(str(user.id)), PolarWebhookEventType.CONTINUOUS_HEART_RATE, ENDPOINT
        )

    assert saved == {"continuous_hr": 2}
    assert len(_polar_samples(db, user.id)) == 2


def _webhook_payload() -> dict[str, Any]:
    return {
        "event": "CONTINUOUS_HEART_RATE",
        "user_id": int(POLAR_USER_ID),
        "date": "2026-09-10",
        "url": f"https://www.polaraccesslink.com{ENDPOINT}",
    }


def test_process_payload_commits_after_saving(db: Session) -> None:
    """The task closes the session without committing, so the handler has to."""
    user = UserFactory()
    UserConnectionFactory(user_id=user.id, provider="polar", provider_user_id=POLAR_USER_ID)
    handler = PolarStrategy().webhooks
    assert isinstance(handler, PolarWebhookHandler)

    events: list[str] = []
    original_fetch = Polar247Data.fetch_and_save_from_webhook
    original_commit = db.commit

    def recording_fetch(self: Polar247Data, *args: Any, **kwargs: Any) -> dict[str, int]:
        saved = original_fetch(self, *args, **kwargs)
        events.append("saved")
        return saved

    def recording_commit() -> None:
        events.append("commit")
        original_commit()

    with (
        patch.object(Polar247Data, "_make_api_request", return_value=DAY_RESPONSE),
        patch.object(Polar247Data, "fetch_and_save_from_webhook", recording_fetch),
        patch.object(db, "commit", recording_commit),
    ):
        result = handler.process_payload(db, _webhook_payload(), "test-trace")

    assert result["status"] == "accepted", result
    assert "commit" in events[events.index("saved") :], events


def test_process_payload_rolls_back_on_error(db: Session) -> None:
    user = UserFactory()
    UserConnectionFactory(user_id=user.id, provider="polar", provider_user_id=POLAR_USER_ID)
    handler = PolarStrategy().webhooks
    assert isinstance(handler, PolarWebhookHandler)

    rolled_back: list[str] = []

    with (
        patch.object(Polar247Data, "fetch_and_save_from_webhook", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", lambda: rolled_back.append("rollback")),
    ):
        result = handler.process_payload(db, _webhook_payload(), "test-trace")

    assert result["status"] == "error"
    assert rolled_back == ["rollback"]
