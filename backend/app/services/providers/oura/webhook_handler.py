"""Oura webhook handler.

Oura sends notify-only webhooks: a lightweight payload containing the user ID,
data type, event type, and object_id of the changed resource. The actual data
is fetched via GET /v2/usercollection/{data_type}/{object_id}.

Signature scheme
----------------
  Message  : timestamp_string + raw_request_body
  Algorithm: HMAC-SHA256(client_secret, message)
  Encoding : hex (upper-case)
  Headers  : x-oura-signature, x-oura-timestamp

Challenge verification
-----------------------
  When a subscription is created, Oura sends a GET request with
  ``verification_token`` and ``challenge`` query params. The handler must
  verify the token and echo the challenge back.

The endpoint must respond quickly; ``dispatch()`` stores the raw payload and
enqueues a Celery task, returning 200 immediately. ``process_payload()`` does
the actual API fetch and DB write, called by the task.

Supported data types
---------------------
  workout / daily_sleep / sleep / daily_readiness / daily_activity / daily_spo2

See: https://cloud.ouraring.com/v2/docs#tag/Webhook-Subscription-Routes
"""

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.oura import OuraWebhookNotification
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.workouts import OuraWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"

SUPPORTED_DATA_TYPES = [
    "workout",
    "sleep",
    "daily_sleep",
    "daily_readiness",
    "daily_activity",
    "daily_spo2",
    "daily_cardiovascular_age",
    "vo2_max",
]

# Oura webhook data_type → REST collection name (only entries that differ)
_COLLECTION_NAME: dict[str, str] = {
    "vo2_max": "vO2_max",
}


class OuraWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Oura notify-only events."""

    def __init__(self, data_247: Oura247Data, workouts: OuraWorkouts) -> None:
        super().__init__("oura")
        self.data_247 = data_247
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify x-oura-signature using HMAC-SHA256 + hex (upper-case)."""
        secret_setting = settings.oura_client_secret
        if not secret_setting:
            log_structured(
                logger,
                "error",
                "OURA_CLIENT_SECRET not configured; rejecting webhook",
                provider="oura",
                action="webhook_signature_missing_secret",
            )
            return False

        signature = request.headers.get("x-oura-signature")
        timestamp = request.headers.get("x-oura-timestamp")

        if not signature or not timestamp:
            log_structured(
                logger,
                "warning",
                "Missing Oura webhook signature headers",
                provider="oura",
                action="webhook_signature_missing",
                has_signature=bool(signature),
                has_timestamp=bool(timestamp),
            )
            return False

        secret = secret_setting.get_secret_value()
        return self._verify_hmac_sha256(
            secret,
            body,
            signature,
            prefix=timestamp.encode(),
            case_insensitive=True,
        )

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Store the raw payload and enqueue async processing. Returns immediately."""
        request_trace_id = str(uuid4())[:8]
        event_type = payload.get("event_type", "unknown")
        data_type = payload.get("data_type", "unknown")
        oura_user_id = payload.get("user_id", "unknown")

        log_structured(
            logger,
            "info",
            "Received Oura webhook",
            provider="oura",
            trace_id=request_trace_id,
            event_type=event_type,
            data_type=data_type,
            oura_user_id=oura_user_id,
        )

        store_raw_payload(source="webhook", provider="oura", payload=payload, trace_id=request_trace_id)

        task = celery_app.send_task(_PROCESS_PUSH_TASK, args=["oura", payload, request_trace_id], queue="webhook_sync")
        log_structured(
            logger,
            "info",
            "Enqueued Oura webhook processing task",
            provider="oura",
            trace_id=request_trace_id,
            task_id=getattr(task, "id", None),
        )

        return {"status": "accepted"}

    def handle_challenge(self, request: Request) -> dict[str, Any]:
        """Handle Oura GET subscription verification challenge.

        Oura sends ``?verification_token=...&challenge=...`` when a subscription
        is created. We verify the token and echo the challenge back.
        """
        expected = settings.oura_webhook_verification_token.get_secret_value()

        verification_token = request.query_params.get("verification_token")
        challenge = request.query_params.get("challenge", "")

        if not verification_token or not self._verify_token(expected, verification_token):
            raise HTTPException(status_code=401, detail="Invalid verification token")

        return {"challenge": challenge}

    def supported_event_types(self) -> list[str]:
        return SUPPORTED_DATA_TYPES

    # ------------------------------------------------------------------
    # Async processing (called by Celery task)
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process an Oura notify-only payload synchronously.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        """
        try:
            notification = OuraWebhookNotification(**payload)
        except (ValidationError, TypeError) as exc:
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        if notification.event_type == "delete":
            log_structured(
                logger,
                "info",
                "Ignoring Oura delete event",
                provider="oura",
                trace_id=trace_id,
                data_type=notification.data_type,
            )
            return {"status": "ignored", "reason": "delete_event"}

        connection = self.connection_repo.get_by_provider_user_id(db, "oura", notification.user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Oura user",
                provider="oura",
                trace_id=trace_id,
                oura_user_id=notification.user_id,
                data_type=notification.data_type,
            )
            return {
                "status": "user_not_found",
                "oura_user_id": notification.user_id,
                "data_type": notification.data_type,
            }

        user_id: UUID = connection.user_id

        log_structured(
            logger,
            "info",
            "Processing Oura webhook notification",
            provider="oura",
            trace_id=trace_id,
            user_id=str(user_id),
            oura_user_id=notification.user_id,
            data_type=notification.data_type,
            event_type=notification.event_type,
            object_id=notification.object_id,
        )

        count = self._dispatch_data_type(db, notification, user_id)

        if count is None:
            log_structured(
                logger,
                "info",
                "Unhandled Oura data type",
                provider="oura",
                trace_id=trace_id,
                data_type=notification.data_type,
                user_id=str(user_id),
            )
            return {"status": "ignored", "reason": f"unhandled_data_type: {notification.data_type}"}

        log_structured(
            logger,
            "info",
            "Oura webhook notification processed",
            provider="oura",
            action="oura_webhook_complete",
            user_id=str(user_id),
            data_type=notification.data_type,
            event_type=notification.event_type,
            records_saved=count,
        )
        return {
            "status": "processed",
            "data_type": notification.data_type,
            "event_type": notification.event_type,
            "records_saved": count,
        }

    # ------------------------------------------------------------------
    # Per-data-type handlers
    # ------------------------------------------------------------------

    def _dispatch_data_type(
        self,
        db: DbSession,
        notification: OuraWebhookNotification,
        user_id: UUID,
    ) -> int | None:
        data_type = notification.data_type
        object_id = notification.object_id

        if not object_id:
            return None

        if data_type == "workout":
            return self.workouts.save_by_id(db, user_id, object_id)

        collection = _COLLECTION_NAME.get(data_type, data_type)
        raw = self.data_247._make_api_request(db, user_id, f"/v2/usercollection/{collection}/{object_id}")
        if not raw or not isinstance(raw, dict):
            return 0

        docs = [raw]

        match data_type:
            case "sleep" | "daily_sleep":
                return self.data_247.save_sleep_data(db, user_id, self.data_247.normalize_sleeps(docs, user_id))
            case "daily_readiness":
                return self.data_247.save_readiness_data(db, user_id, self.data_247.normalize_readiness(docs, user_id))
            case "daily_activity":
                return self.data_247.save_activity_data(
                    db, user_id, self.data_247.normalize_activity_samples(docs, user_id)
                )
            case "daily_spo2":
                return self.data_247.save_spo2_data(db, user_id, docs)
            case "daily_cardiovascular_age":
                return self.data_247.save_cardiovascular_age_data(
                    db, user_id, self.data_247.normalize_cardiovascular_age_samples(docs, user_id)
                )
            case "vo2_max":
                return self.data_247.save_vo2_data(db, user_id, docs)
            case _:
                return None
