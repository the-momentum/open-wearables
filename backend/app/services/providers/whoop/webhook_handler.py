"""Whoop webhook handler.

Whoop sends notify-only webhooks: a lightweight payload containing the resource
ID and event type. The actual data must be fetched via the REST API.

Signature scheme
----------------
  Message  : timestamp_ms_string + raw_request_body
  Algorithm: HMAC-SHA256(client_secret, message)
  Encoding : base64
  Headers  : X-WHOOP-Signature, X-WHOOP-Signature-Timestamp

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
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.whoop import WhoopWebhookNotification, WhoopWebhookNotificationType
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.workouts import WhoopWorkouts
from app.utils.structured_logging import log_structured


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
        secret_setting = settings.whoop_webhook_client_secret
        if not secret_setting:
            log_structured(
                self.logger,
                "warning",
                "whoop_webhook_client_secret not configured; skipping signature verification",
                provider="whoop",
                action="webhook_signature_skipped",
            )
            return True

        signature = request.headers.get("X-WHOOP-Signature")
        timestamp = request.headers.get("X-WHOOP-Signature-Timestamp")

        if not signature or not timestamp:
            log_structured(
                self.logger,
                "warning",
                "Missing Whoop webhook signature headers",
                provider="whoop",
                action="webhook_signature_missing",
                has_signature=bool(signature),
                has_timestamp=bool(timestamp),
            )
            return False

        secret = secret_setting.get_secret_value()
        mac = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256)
        expected = base64.b64encode(mac.digest()).decode()
        return hmac.compare_digest(expected, signature)

    def parse_payload(self, body: bytes) -> WhoopWebhookNotification:
        try:
            data = json.loads(body)
            return WhoopWebhookNotification(**data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid Whoop webhook payload: {exc}") from exc

    def dispatch(self, db: DbSession, payload: WhoopWebhookNotification) -> dict[str, Any]:
        connection = self.connection_repo.get_by_provider_user_id(db, "whoop", str(payload.user_id))
        if not connection:
            log_structured(
                self.logger,
                "warning",
                "No connection found for Whoop user",
                action="whoop_webhook_user_not_found",
                whoop_user_id=payload.user_id,
                event_type=payload.type,
            )
            return {"status": "ignored", "reason": "user_not_connected"}

        internal_user_id: UUID = connection.user_id
        resource_id = str(payload.id)

        log_structured(
            self.logger,
            "info",
            "Processing Whoop webhook notification",
            action="whoop_webhook_processing",
            user_id=str(internal_user_id),
            whoop_user_id=payload.user_id,
            event_type=payload.type,
            resource_id=resource_id,
            trace_id=payload.trace_id,
        )

        if payload.type.is_delete_type:
            return self._handle_deleted(db, payload.type, internal_user_id, resource_id)
        elif payload.type.is_update_type:
            return self._handle_updated(db, payload.type, internal_user_id, resource_id)
        else:
            log_structured(
                self.logger,
                "info",
                "Unhandled Whoop webhook event type",
                action="whoop_webhook_unhandled",
                event_type=payload.type,
                user_id=str(internal_user_id),
            )
            return {"status": "ignored", "reason": f"unhandled_event_type: {payload.type}"}

    # ------------------------------------------------------------------
    # Private dispatch helpers
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
                log_structured(
                    self.logger,
                    "info",
                    "Unhandled Whoop event type",
                    action="whoop_webhook_unhandled",
                    event_type=event_type,
                    user_id=str(user_id),
                )
                return {"status": "ignored", "reason": f"unhandled_event_type: {event_type}"}

        log_structured(
            self.logger,
            "info",
            "Whoop webhook notification processed",
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
        """Find the EventRecord by external_id and delete it.

        Recovery records are stored as DataPointSeries (no external_id index),
        so recovery.deleted is logged but not actioned.
        """
        if event_type == WhoopWebhookNotificationType.RECOVERY_DELETED:
            log_structured(
                self.logger,
                "info",
                "Ignoring recovery.deleted (recovery stored as time-series, no external_id index)",
                action="whoop_webhook_recovery_delete_skipped",
                user_id=str(user_id),
                resource_id=resource_id,
            )
            return {"status": "ignored", "reason": "recovery_delete_not_supported"}

        deleted = self.data_247.event_record_repo.delete_by_external_id(
            db, user_id, resource_id, source="whoop"
        )
        if not deleted:
            log_structured(
                self.logger,
                "info",
                "No EventRecord found for deleted Whoop resource",
                action="whoop_webhook_delete_not_found",
                event_type=event_type,
                user_id=str(user_id),
                resource_id=resource_id,
            )
            return {"status": "ignored", "reason": "record_not_found"}

        log_structured(
            self.logger,
            "info",
            "Deleted EventRecord for Whoop resource",
            action="whoop_webhook_deleted",
            event_type=event_type,
            user_id=str(user_id),
            resource_id=resource_id,
        )
        return {"status": "deleted", "event_type": event_type, "resource_id": resource_id}
