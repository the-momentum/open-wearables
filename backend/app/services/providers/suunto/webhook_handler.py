"""Suunto webhook handler.

Suunto delivers data inline (PUSH mode) for all event types:
- WORKOUT_CREATED: full workout object + gear; we fetch the canonical record via
  REST using the workoutKey so we always get the schema we expect.
- SUUNTO_247_SLEEP_CREATED / SUUNTO_247_ACTIVITY_CREATED / SUUNTO_247_RECOVERY_CREATED:
  full samples array delivered in-band; processed directly.
- ROUTE_CREATED: ignored (routes are not stored).

Signature verification uses HMAC-SHA256 of the raw request body with the
app's notification secret, delivered in the ``X-HMAC-SHA256-Signature`` header.

The endpoint must respond within 2 seconds; ``dispatch()`` stores the raw
payload and enqueues a Celery task, returning 200 immediately.
"""

import json
import logging
from typing import Any
from uuid import uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.services.providers.suunto.data_247 import Suunto247Data
from app.services.providers.suunto.workouts import SuuntoWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

SUPPORTED_EVENT_TYPES: list[str] = [
    "WORKOUT_CREATED",
    "ROUTE_CREATED",
    "SUUNTO_247_ACTIVITY_CREATED",
    "SUUNTO_247_SLEEP_CREATED",
    "SUUNTO_247_RECOVERY_CREATED",
]

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"


class SuuntoWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Suunto Sports Tracker API push events.

    Suunto signs each request body with HMAC-SHA256 and delivers the result in
    the ``X-HMAC-SHA256-Signature`` request header.
    """

    def __init__(self, suunto_workouts: SuuntoWorkouts, suunto_247: Suunto247Data) -> None:
        super().__init__("suunto")
        self.suunto_workouts = suunto_workouts
        self.suunto_247 = suunto_247
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        secret = settings.suunto_webhook_secret
        if not secret:
            # suunto_webhook_secret is always derived from secret_key at startup,
            # so this branch is only reachable in misconfigured test environments.
            log_structured(
                logger,
                "warning",
                "SUUNTO_WEBHOOK_SECRET not configured — rejecting webhook",
                provider="suunto",
                action="webhook_signature_missing_secret",
            )
            return False

        provided = request.headers.get("X-HMAC-SHA256-Signature", "")
        if not provided:
            log_structured(
                logger,
                "warning",
                "Missing X-HMAC-SHA256-Signature header",
                provider="suunto",
                action="webhook_signature_invalid",
            )
            return False

        return self._verify_hmac_sha256(secret.get_secret_value(), body, provided)

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        """Accept the webhook and enqueue async processing.

        Returns immediately so Suunto's 2-second timeout is never exceeded.
        """
        request_trace_id = str(uuid4())[:8]
        event_type = payload.get("type", "unknown")
        username = payload.get("username", "unknown")

        log_structured(
            logger,
            "info",
            "Received Suunto webhook",
            provider="suunto",
            trace_id=request_trace_id,
            event_type=event_type,
            suunto_username=username,
        )

        store_raw_payload(source="webhook", provider="suunto", payload=payload, trace_id=request_trace_id)

        task = celery_app.send_task(
            _PROCESS_PUSH_TASK, args=["suunto", payload, request_trace_id], queue="webhook_sync"
        )
        log_structured(
            logger,
            "info",
            "Enqueued Suunto webhook processing task",
            provider="suunto",
            trace_id=request_trace_id,
            task_id=getattr(task, "id", None),
        )

        return {"status": "accepted"}

    def supported_event_types(self) -> list[str]:
        return SUPPORTED_EVENT_TYPES

    # ------------------------------------------------------------------
    # Async processing (called by Celery task)
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process a Suunto PUSH payload synchronously.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        """
        event_type = payload.get("type", "")
        username = payload.get("username", "")

        if not username:
            return {"status": "error", "error": "Missing username in payload", "event_type": event_type}

        connection = self.connection_repo.get_by_provider_username(db, "suunto", username)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Suunto user",
                provider="suunto",
                trace_id=trace_id,
                suunto_username=username,
            )
            return {"status": "user_not_found", "suunto_username": username, "event_type": event_type}

        user_id = connection.user_id

        log_structured(
            logger,
            "info",
            "Processing Suunto webhook event",
            provider="suunto",
            trace_id=trace_id,
            event_type=event_type,
            user_id=str(user_id),
        )

        result: dict[str, Any] = {"event_type": event_type, "user_id": str(user_id)}

        if event_type == "WORKOUT_CREATED":
            result.update(self._process_workout(db, user_id, payload, trace_id))
        elif event_type == "SUUNTO_247_SLEEP_CREATED":
            result.update(self._process_sleep(db, user_id, payload, trace_id))
        elif event_type == "SUUNTO_247_ACTIVITY_CREATED":
            result.update(self._process_activity(db, user_id, payload, trace_id))
        elif event_type == "SUUNTO_247_RECOVERY_CREATED":
            result.update(self._process_recovery(db, user_id, payload, trace_id))
        elif event_type == "ROUTE_CREATED":
            result["status"] = "skipped"
        else:
            log_structured(
                logger,
                "warning",
                "Unknown Suunto event type",
                provider="suunto",
                trace_id=trace_id,
                event_type=event_type,
            )
            result["status"] = "unknown_event_type"

        self.connection_repo.update_last_synced_at(db, connection)
        db.commit()

        return result

    # ------------------------------------------------------------------
    # Per-event-type handlers
    # ------------------------------------------------------------------

    def _process_workout(self, db: DbSession, user_id: Any, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Fetch and save a new workout via the REST API using workoutKey."""
        workout_data = payload.get("workout", {})
        workout_key = workout_data.get("workoutKey") or workout_data.get("workoutId")

        if not workout_key:
            return {"status": "error", "error": "Missing workoutKey in WORKOUT_CREATED payload"}

        log_structured(
            logger,
            "info",
            "Fetching Suunto workout via REST",
            provider="suunto",
            trace_id=trace_id,
            workout_key=workout_key,
            user_id=str(user_id),
        )

        try:
            raw_detail = self.suunto_workouts.get_workout_detail(db, user_id, str(workout_key))
            # REST response wraps workout in 'payload' list
            workouts_list = raw_detail.get("payload", [raw_detail]) if isinstance(raw_detail, dict) else [raw_detail]
            saved = 0
            for raw in workouts_list:
                self.suunto_workouts._process_single_workout(db, user_id, raw)
                saved += 1
            return {"status": "saved", "workout_key": str(workout_key), "saved_count": saved}
        except Exception as exc:
            log_structured(
                logger,
                "error",
                "Failed to fetch/save Suunto workout",
                provider="suunto",
                trace_id=trace_id,
                workout_key=str(workout_key),
                user_id=str(user_id),
                error=str(exc),
            )
            raise

    def _process_sleep(self, db: DbSession, user_id: Any, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Save inline sleep samples from a SUUNTO_247_SLEEP_CREATED event."""
        samples = payload.get("samples", [])
        saved = 0
        for sample in samples:
            try:
                normalized = self.suunto_247.normalize_sleep(sample, user_id)
                self.suunto_247.save_sleep_data(db, user_id, normalized)
                saved += 1
            except Exception as exc:
                log_structured(
                    logger,
                    "warning",
                    "Failed to save Suunto sleep sample",
                    provider="suunto",
                    trace_id=trace_id,
                    user_id=str(user_id),
                    error=str(exc),
                )
        return {"status": "saved", "saved_count": saved, "total_samples": len(samples)}

    def _process_activity(self, db: DbSession, user_id: Any, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Save inline activity samples from a SUUNTO_247_ACTIVITY_CREATED event."""
        samples = payload.get("samples", [])
        try:
            normalized = self.suunto_247.normalize_activity_samples(samples, user_id)
            saved = self.suunto_247.save_activity_samples(db, user_id, normalized)
            return {"status": "saved", "saved_count": saved, "total_samples": len(samples)}
        except Exception as exc:
            log_structured(
                logger,
                "error",
                "Failed to save Suunto activity samples",
                provider="suunto",
                trace_id=trace_id,
                user_id=str(user_id),
                error=str(exc),
            )
            raise

    def _process_recovery(self, db: DbSession, user_id: Any, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Save inline recovery samples from a SUUNTO_247_RECOVERY_CREATED event."""
        samples = payload.get("samples", [])
        saved = 0
        for sample in samples:
            try:
                normalized = self.suunto_247.normalize_recovery(sample, user_id)
                saved += self.suunto_247.save_recovery_data(db, user_id, normalized)
            except Exception as exc:
                log_structured(
                    logger,
                    "warning",
                    "Failed to save Suunto recovery sample",
                    provider="suunto",
                    trace_id=trace_id,
                    user_id=str(user_id),
                    error=str(exc),
                )
        return {"status": "saved", "saved_count": saved, "total_samples": len(samples)}
