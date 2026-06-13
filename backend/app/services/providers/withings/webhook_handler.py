"""Withings notify-only webhook handler.

Notifications arrive form-encoded (``userid, appli, startdate, enddate``) and
unsigned; authenticity rests on the ``userid`` mapping to a known connection.
The handler acknowledges immediately and defers the REST fetch to the shared
``process_webhook_push`` task, keeping the request within Withings' callback
timeout. ``subscribe`` also probes the callback URL with HEAD, answered by
``handle_challenge``.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from celery import current_app as celery_app
from fastapi import Request
from pydantic import ValidationError

from app.database import DbSession, SessionLocal
from app.repositories import UserConnectionRepository
from app.schemas.providers.withings import WithingsNotification
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.workouts import WithingsWorkouts
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"

# Withings ``appli`` notification category → internal domain. Official categories:
# https://developer.withings.com/developer-guide/v3/data-api/notifications/notification-content/
#   1  = Body & Weight           -> getmeas
#   4  = Blood Pressure & HR     -> getmeas
#   16 = Activity (incl workouts)-> getactivity + getworkouts
#   44 = Sleep                   -> getsummary
#   46 = User profile change     -> not a data event (handled as ignore)
_APPLI_DOMAIN: dict[int, str] = {
    1: "measures",
    4: "measures",
    16: "activity_workouts",
    44: "sleep",
}
_PROFILE_CHANGE_APPLI = 46


class WithingsWebhookHandler(BaseWebhookHandler):
    """Notify-only handler for Withings."""

    def __init__(self, data_247: Withings247Data, workouts: WithingsWorkouts) -> None:
        super().__init__("withings")
        self.data_247 = data_247
        # appli 16 covers both daily activity and workouts.
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ---------------------- inbound request handling ----------------------

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        parsed = parse_qs(body.decode("utf-8"))
        return {k: v[0] for k, v in parsed.items()}

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Authenticity = ``userid`` maps to a known connection (no HMAC available).

        Opens its own session because the interface returns only a bool here.
        """
        payload = self.parse_payload(body)
        userid = payload.get("userid")
        if not userid:
            return False
        with SessionLocal() as db:
            return self.connection_repo.get_by_provider_user_id(db, "withings", userid) is not None

    def handle_challenge(self, request: Request) -> dict[str, Any]:
        """Return 200 for the subscribe-time GET/HEAD reachability probe."""
        return {}

    def supported_event_types(self) -> list[str]:
        return [str(a) for a in _APPLI_DOMAIN]

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Acknowledge, then enqueue the data fetch on the ``webhook_sync`` queue."""
        store_raw_payload(source="webhook", provider="withings", payload=payload, trace_id=str(payload.get("userid")))

        try:
            notification = WithingsNotification.model_validate(payload)
        except ValidationError:
            return {"status": "ignored", "reason": "invalid_payload_fields"}

        # appli 46 = user profile change (delete / unlink / update) — not a data event.
        if notification.appli == _PROFILE_CHANGE_APPLI:
            return {"status": "ignored", "reason": "profile_change", "action": notification.action}

        if notification.appli not in _APPLI_DOMAIN:
            return {"status": "ignored", "reason": f"unhandled_appli: {notification.appli}"}

        # Require an explicit range; never fall back to a full-history fetch.
        if notification.startdate is None or notification.enddate is None:
            return {"status": "ignored", "reason": "missing_date_range"}

        celery_app.send_task(
            _PROCESS_PUSH_TASK,
            args=["withings", payload, str(notification.userid)],
            queue="webhook_sync",
        )
        return {"status": "accepted", "appli": notification.appli}

    # ---------------------- async processing (Celery worker) ----------------------

    def process_payload(self, db: DbSession, payload: Any, trace_id: str) -> dict[str, Any]:
        """Fetch and persist the data referenced by a notification.

        Called by the ``process_webhook_push`` Celery task with its own session.
        Re-resolves the user from ``userid`` (the inbound payload is untrusted)
        and pulls the affected domain over ``[startdate, enddate]``.
        """
        try:
            notification = WithingsNotification.model_validate(payload)
        except ValidationError:
            return {"status": "ignored", "reason": "invalid_payload_fields"}

        connection = self.connection_repo.get_by_provider_user_id(db, "withings", notification.userid)
        if not connection:
            return {"status": "user_not_found", "withings_user_id": notification.userid}

        domain = _APPLI_DOMAIN.get(notification.appli)
        if domain is None:
            return {"status": "ignored", "reason": f"unhandled_appli: {notification.appli}"}
        if notification.startdate is None or notification.enddate is None:
            return {"status": "ignored", "reason": "missing_date_range"}

        user_id = connection.user_id
        start = datetime.fromtimestamp(notification.startdate, tz=timezone.utc)
        end = datetime.fromtimestamp(notification.enddate, tz=timezone.utc)

        if domain == "measures":
            # appli 1 (body/weight) and 4 (blood pressure + heart rate) both via getmeas.
            saved = self.data_247.save_measures(db, user_id, start, end)
        elif domain == "sleep":
            saved = self.data_247.save_sleep(db, user_id, start, end)
        else:
            # appli 16 covers both daily activity and workouts.
            saved = self.data_247.save_activity(db, user_id, start, end)
            saved += self.workouts.load_data(db, user_id, start_date=start.isoformat(), end_date=end.isoformat())

        log_structured(
            logger,
            "info",
            "Withings webhook processed",
            provider="withings",
            appli=notification.appli,
            domain=domain,
            user_id=str(user_id),
            records=saved,
            trace_id=trace_id,
        )
        return {"status": "processed", "domain": domain, "records_saved": saved}
