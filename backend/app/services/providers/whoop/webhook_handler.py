"""Whoop webhook handler.

Whoop sends notify-only webhooks: a lightweight payload containing the resource
ID and event type. The actual data must be fetched via the REST API.

Signature scheme
----------------
  Message  : timestamp_ms_string + raw_request_body
  Algorithm: HMAC-SHA256(client_secret, message)
  Encoding : base64
  Headers  : X-WHOOP-Signature, X-WHOOP-Signature-Timestamp

The endpoint must respond quickly; ``dispatch()`` stores the raw payload and
enqueues a Celery task, returning 200 immediately. ``process_payload()`` does
the actual API fetch and DB write, called by the task.

Supported event types
---------------------
  workout.updated / workout.deleted
  sleep.updated   / sleep.deleted
  recovery.updated / recovery.deleted

See: https://developer.whoop.com/docs/developing/webhooks/
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.whoop import WhoopWebhookNotification, WhoopWebhookNotificationType
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.workouts import WhoopWorkouts
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"


class WhoopWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Whoop notify-only events."""

    def __init__(self, data_247: Whoop247Data, workouts: WhoopWorkouts) -> None:
        super().__init__("whoop")
        self.data_247 = data_247
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify X-WHOOP-Signature using HMAC-SHA256 + base64."""
        secret_setting = settings.whoop_client_secret
        if not secret_setting:
            log_structured(
                logger,
                "error",
                "WHOOP_CLIENT_SECRET not configured; rejecting webhook",
                provider="whoop",
                action="webhook_signature_missing_secret",
            )
            return False

        signature = request.headers.get("X-WHOOP-Signature")
        timestamp = request.headers.get("X-WHOOP-Signature-Timestamp")

        if not signature or not timestamp:
            log_structured(
                logger,
                "warning",
                "Missing Whoop webhook signature headers",
                provider="whoop",
                action="webhook_signature_missing",
                has_signature=bool(signature),
                has_timestamp=bool(timestamp),
            )
            return False

        try:
            ts_seconds = int(timestamp) / 1000
        except ValueError:
            log_structured(
                logger,
                "warning",
                "Unparsable X-WHOOP-Signature-Timestamp",
                provider="whoop",
                action="webhook_signature_timestamp_unparsable",
                timestamp=timestamp,
            )
            return False

        if abs(time.time() - ts_seconds) > 300:
            log_structured(
                logger,
                "warning",
                "Stale Whoop webhook timestamp",
                provider="whoop",
                action="webhook_signature_stale",
                timestamp=timestamp,
            )
            return False

        secret = secret_setting.get_secret_value()
        mac = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256)
        expected = base64.b64encode(mac.digest()).decode()
        return hmac.compare_digest(expected, signature)

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Store the raw payload and enqueue async processing. Returns immediately."""
        request_trace_id = str(uuid4())[:8]
        event_type = payload.get("type", "unknown")
        whoop_user_id = payload.get("user_id", "unknown")

        log_structured(
            logger,
            "info",
            "Received Whoop webhook",
            provider="whoop",
            trace_id=request_trace_id,
            event_type=event_type,
            whoop_user_id=whoop_user_id,
        )

        store_raw_payload(source="webhook", provider="whoop", payload=payload, trace_id=request_trace_id)

        task = celery_app.send_task(_PROCESS_PUSH_TASK, args=["whoop", payload, request_trace_id], queue="webhook_sync")
        log_structured(
            logger,
            "info",
            "Enqueued Whoop webhook processing task",
            provider="whoop",
            trace_id=request_trace_id,
            task_id=getattr(task, "id", None),
        )

        return {"status": "accepted"}

    def supported_event_types(self) -> list[str]:
        return list(WhoopWebhookNotificationType)

    # ------------------------------------------------------------------
    # Async processing (called by Celery task)
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process a Whoop notify-only payload synchronously.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        """
        try:
            notification = WhoopWebhookNotification(**payload)
        except (ValidationError, TypeError) as exc:
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        connection = self.connection_repo.get_by_provider_user_id(db, "whoop", str(notification.user_id))
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Whoop user",
                provider="whoop",
                trace_id=trace_id,
                whoop_user_id=notification.user_id,
                event_type=notification.type,
            )
            return {"status": "user_not_found", "whoop_user_id": notification.user_id, "event_type": notification.type}

        user_id: UUID = connection.user_id
        resource_id = str(notification.id)

        log_structured(
            logger,
            "info",
            "Processing Whoop webhook notification",
            provider="whoop",
            trace_id=trace_id,
            user_id=str(user_id),
            whoop_user_id=notification.user_id,
            event_type=notification.type,
            resource_id=resource_id,
        )

        if notification.type.is_delete_type:
            return self._handle_deleted(db, notification.type, user_id, resource_id)
        if notification.type.is_update_type:
            return self._handle_updated(db, notification.type, user_id, resource_id)

        log_structured(
            logger,
            "info",
            "Unhandled Whoop webhook event type",
            provider="whoop",
            trace_id=trace_id,
            event_type=notification.type,
            user_id=str(user_id),
        )
        return {"status": "ignored", "reason": f"unhandled_event_type: {notification.type}"}

    # ------------------------------------------------------------------
    # Per-event-type handlers
    # ------------------------------------------------------------------

    def _handle_updated(
        self,
        db: DbSession,
        event_type: WhoopWebhookNotificationType,
        user_id: UUID,
        resource_id: str,
    ) -> dict[str, Any]:
        """Fetch the specific resource from the Whoop API and save it."""
        match event_type:
            case WhoopWebhookNotificationType.WORKOUT_UPDATED:
                count = self.workouts.load_single_workout(db, user_id, resource_id)
            case WhoopWebhookNotificationType.SLEEP_UPDATED:
                count = self.data_247.load_single_sleep(db, user_id, resource_id)
            case WhoopWebhookNotificationType.RECOVERY_UPDATED:
                count = self.data_247.load_single_recovery(db, user_id, resource_id)
            case _:
                return {"status": "ignored", "reason": f"unhandled_event_type: {event_type}"}

        log_structured(
            logger,
            "info",
            "Whoop webhook notification processed",
            provider="whoop",
            action="whoop_webhook_complete",
            user_id=str(user_id),
            event_type=event_type,
            records_saved=count,
        )
        return {"status": "processed", "event_type": event_type, "records_saved": count}

    def _handle_deleted(
        self,
        db: DbSession,
        event_type: WhoopWebhookNotificationType,
        user_id: UUID,
        resource_id: str,
    ) -> dict[str, Any]:
        """Delete the EventRecord matching external_id.

        Recovery is stored as DataPointSeries (no external_id index), so
        recovery.deleted is logged but not actioned.
        """
        if event_type == WhoopWebhookNotificationType.RECOVERY_DELETED:
            log_structured(
                logger,
                "info",
                "Ignoring recovery.deleted (recovery stored as time-series, no external_id index)",
                provider="whoop",
                action="whoop_webhook_recovery_delete_skipped",
                user_id=str(user_id),
                resource_id=resource_id,
            )
            return {"status": "ignored", "reason": "recovery_delete_not_supported"}

        deleted = self.data_247.event_record_repo.delete_by_external_id(db, user_id, resource_id, source="whoop")
        if not deleted:
            log_structured(
                logger,
                "info",
                "No EventRecord found for deleted Whoop resource",
                provider="whoop",
                action="whoop_webhook_delete_not_found",
                event_type=event_type,
                user_id=str(user_id),
                resource_id=resource_id,
            )
            return {"status": "ignored", "reason": "record_not_found"}

        log_structured(
            logger,
            "info",
            "Deleted EventRecord for Whoop resource",
            provider="whoop",
            action="whoop_webhook_deleted",
            event_type=event_type,
            user_id=str(user_id),
            resource_id=resource_id,
        )
        return {"status": "deleted", "event_type": event_type, "resource_id": resource_id}
