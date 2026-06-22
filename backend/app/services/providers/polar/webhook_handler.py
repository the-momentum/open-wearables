"""Polar webhook handler.

Polar sends notify-only webhooks: a lightweight payload containing the event
type, Polar user ID, entity ID, and a URL pointing to the specific entity.
The handler fetches exactly that URL and saves the result.

Signature scheme
----------------
  Header   : Polar-Webhook-Signature: <hex_digest>
  Message  : raw request body
  Algorithm: HMAC-SHA256(webhook_secret from provider_settings, body)

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
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from uuid import uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.database import DbSession, SessionLocal
from app.repositories import UserConnectionRepository
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.enums import ProviderName
from app.schemas.providers.polar import PolarWebhookEvent, PolarWebhookEventType
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

if TYPE_CHECKING:
    from app.services.providers.polar.data_247 import Polar247Data
    from app.services.providers.polar.workouts import PolarWorkouts

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"


class PolarWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Polar AccessLink notify-only events."""

    def __init__(self, workouts: "PolarWorkouts | None" = None, data_247: "Polar247Data | None" = None) -> None:
        super().__init__("polar")
        self.connection_repo = UserConnectionRepository()
        self.provider_settings_repo = ProviderSettingsRepository()
        self.workouts = workouts
        self.data_247 = data_247

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify HMAC-SHA256 signature from Polar-Webhook-Signature header."""
        with SessionLocal() as db:
            secret = self.provider_settings_repo.get_webhook_secret(db, ProviderName.POLAR)

        if not secret:
            log_structured(logger, "warning", "Polar webhook signature secret not configured", provider="polar")
            return False

        provided_signature = request.headers.get("Polar-Webhook-Signature", "")
        if not provided_signature:
            return False

        return self._verify_hmac_sha256(secret, body, provided_signature)

    def parse_payload(self, body: bytes) -> PolarWebhookEvent:
        try:
            data = json.loads(body)
            return PolarWebhookEvent(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body") from exc
        except (ValidationError, TypeError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid payload: {exc}") from exc

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
        return list(PolarWebhookEventType)

    # ------------------------------------------------------------------
    # Async processing
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Fetch the entity at the webhook URL and save it.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        Uses ``event.url`` to make a targeted single-entity request instead of a
        broad range sync.
        """
        try:
            event = PolarWebhookEvent(**payload)
        except (ValidationError, TypeError) as exc:
            log_structured(
                logger,
                "error",
                "Invalid Polar webhook payload",
                provider="polar",
                trace_id=trace_id,
                error=str(exc),
            )
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        if event.event == "PING":
            return {"status": "ignored", "reason": "ping"}

        if not event.user_id:
            log_structured(
                logger,
                "warning",
                "Polar webhook event missing user_id",
                provider="polar",
                trace_id=trace_id,
                event=event.event,
            )
            return {"status": "error", "error": "missing user_id"}

        connection = self.connection_repo.get_by_provider_user_id(db, "polar", str(event.user_id))
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Polar user",
                provider="polar",
                trace_id=trace_id,
                polar_user_id=event.user_id,
            )
            return {"status": "user_not_found", "polar_user_id": event.user_id}

        if not event.url:
            log_structured(
                logger,
                "warning",
                "Polar webhook event missing url",
                provider="polar",
                trace_id=trace_id,
                event=event.event,
            )
            return {"status": "error", "error": "missing url"}

        path = urlparse(event.url).path
        user_id = connection.user_id

        self.connection_repo.update_last_synced_at(db, connection)

        log_structured(
            logger,
            "info",
            "Fetching Polar entity from webhook URL",
            provider="polar",
            trace_id=trace_id,
            event=event.event,
            path=path,
            user_id=str(user_id),
        )

        try:
            if event.event == PolarWebhookEventType.EXERCISE:
                if not self.workouts:
                    return {"status": "error", "error": "workouts service not initialised"}
                saved = self.workouts.fetch_and_save_exercise(db, user_id, path)
                return {"status": "accepted", "user_id": str(user_id), "saved": {"exercises": saved}}

            if not self.data_247:
                return {"status": "error", "error": "data_247 service not initialised"}
            saved = self.data_247.fetch_and_save_from_webhook(db, user_id, event.event, path)
            return {"status": "accepted", "user_id": str(user_id), "saved": saved}
        except Exception as exc:
            log_and_capture_error(
                exc,
                logger,
                "Error fetching/saving Polar webhook data",
                extra={
                    "provider": "polar",
                    "trace_id": trace_id,
                    "event": event.event,
                    "polar_user_id": event.user_id,
                    "path": path,
                    "user_id": str(user_id),
                },
            )
            return {"status": "error", "error": str(exc), "user_id": str(user_id)}
