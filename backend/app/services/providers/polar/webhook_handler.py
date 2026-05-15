"""Polar webhook handler.

Polar sends notify-only webhooks: a lightweight payload containing the event
type, Polar user ID, and entity ID. Full data must be fetched via the AccessLink
API after receiving the notification.

Signature scheme
----------------
  Header   : X-Polar-Webhook-Signature: <hex_digest>
  Message  : raw request body
  Algorithm: HMAC-SHA256(polar_webhook_signature_secret, body)

Ping verification
-----------------
  When registering a webhook, Polar POSTs {"event": "PING"} to the configured
  URL. This must be answered with HTTP 200 before the webhook is created.
  The ping is sent without a signature header so it bypasses verification.

Delivery model
--------------
  ``dispatch()`` acknowledges the event immediately and enqueues a Celery task.
  ``process_payload()`` does the actual AccessLink API fetch and DB write,
  called by the shared ``process_webhook_push`` task.

Supported event types
---------------------
  EXERCISE, SLEEP, CONTINUOUS_HEART_RATE, ACTIVITY_SUMMARY,
  SLEEP_WISE_ALERTNESS, SLEEP_WISE_CIRCADIAN_BEDTIME, PHYSICAL_INFORMATION

See: https://www.polar.com/accesslink-api/#webhooks
"""

import json
import logging
from typing import Any
from uuid import uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.polar.webhook import PolarWebhookEvent
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"
_SIGNATURE_HEADER = "X-Polar-Webhook-Signature"

# Maps Polar event types to sync task data_type values
_EVENT_TO_DATA_TYPE: dict[str, str] = {
    "EXERCISE": "exercises",
    "SLEEP": "sleep",
    "CONTINUOUS_HEART_RATE": "continuous_hr",
    "ACTIVITY_SUMMARY": "daily_activity",
    "SLEEP_WISE_ALERTNESS": "alertness",
    "SLEEP_WISE_CIRCADIAN_BEDTIME": "circadian_bedtime",
    "PHYSICAL_INFORMATION": "all",
}

_SYNC_TASK = "app.integrations.celery.tasks.sync_vendor_data_task.sync_vendor_data"


class PolarWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Polar AccessLink notify-only events."""

    def __init__(self) -> None:
        super().__init__("polar")
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify HMAC-SHA256 signature from X-Polar-Webhook-Signature header."""
        secret = (
            settings.polar_webhook_signature_secret.get_secret_value()
            if settings.polar_webhook_signature_secret
            else None
        )
        if not secret:
            log_structured(logger, "warning", "Polar webhook signature secret not configured", provider="polar")
            return False

        provided = request.headers.get(_SIGNATURE_HEADER, "")
        if not provided:
            return False

        return self._verify_hmac_sha256(secret, body, provided)

    def parse_payload(self, body: bytes) -> PolarWebhookEvent:
        try:
            data = json.loads(body)
            return PolarWebhookEvent(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        except (ValidationError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc

    def handle(self, request: Request, body: bytes, db: DbSession) -> dict[str, Any]:
        """Override to handle PING before signature verification."""
        try:
            data = json.loads(body)
            event = data.get("event", "")
        except (json.JSONDecodeError, ValueError):
            event = ""

        if event == "PING":
            log_structured(logger, "info", "Polar webhook ping received", provider="polar")
            return {"status": "ok"}

        return super().handle(request, body, db)

    def dispatch(self, db: DbSession, payload: PolarWebhookEvent) -> dict[str, Any]:
        """Store raw payload and enqueue async processing. Returns 200 immediately."""
        trace_id = str(uuid4())[:8]
        raw = payload.model_dump()

        log_structured(
            logger,
            "info",
            "Received Polar webhook event",
            provider="polar",
            trace_id=trace_id,
            event=payload.event,
            polar_user_id=payload.user_id,
            entity_id=payload.entity_id,
        )

        store_raw_payload(source="webhook", provider="polar", payload=raw, trace_id=trace_id)

        task = celery_app.send_task(_PROCESS_PUSH_TASK, args=["polar", raw, trace_id], queue="webhook_sync")
        log_structured(
            logger,
            "info",
            "Enqueued Polar webhook processing task",
            provider="polar",
            trace_id=trace_id,
            task_id=getattr(task, "id", None),
        )

        return {"status": "accepted"}

    def supported_event_types(self) -> list[str]:
        return list(_EVENT_TO_DATA_TYPE.keys()) + ["PING"]

    # ------------------------------------------------------------------
    # Async processing
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process a Polar notify-only payload.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        Looks up the user by Polar user ID and enqueues a targeted sync.
        """
        try:
            event = PolarWebhookEvent(**payload)
        except (ValidationError, TypeError) as exc:
            log_structured(
                logger, "error", "Invalid Polar webhook payload",
                provider="polar", trace_id=trace_id, error=str(exc),
            )
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        if event.event == "PING":
            return {"status": "ignored", "reason": "ping"}

        if not event.user_id:
            log_structured(
                logger, "warning", "Polar webhook event missing user_id",
                provider="polar", trace_id=trace_id, event=event.event,
            )
            return {"status": "error", "error": "missing user_id"}

        connection = self.connection_repo.get_by_provider_user_id(db, "polar", event.user_id)
        if not connection:
            log_structured(
                logger, "warning", "No connection found for Polar user",
                provider="polar", trace_id=trace_id, polar_user_id=event.user_id,
            )
            return {"status": "user_not_found", "polar_user_id": event.user_id}

        data_type = _EVENT_TO_DATA_TYPE.get(event.event, "all")
        user_id = str(connection.user_id)

        log_structured(
            logger,
            "info",
            "Triggering Polar sync from webhook",
            provider="polar",
            trace_id=trace_id,
            user_id=user_id,
            event=event.event,
            data_type=data_type,
        )

        celery_app.send_task(
            _SYNC_TASK,
            kwargs={"user_id": user_id, "provider": "polar", "data_type": data_type},
            queue="sync",
        )

        return {"status": "accepted", "user_id": user_id, "data_type": data_type}
