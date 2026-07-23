"""Google Health API webhook handler.

Google sends notify-only pings: each notification names the changed ``dataType`` and
the physical-time ``intervals`` that changed, but carries no data. We fetch the actual
data via REST (rollUp/list, or the sleep/exercise session endpoints) over those
intervals, then persist it.

Authentication
--------------
Google echoes a bearer secret (configured on the subscriber) in the ``Authorization``
header of every request. We compare it against ``settings.google_webhook_secret``.
(Asymmetric ``GOOGLE-HEALTH-API-SIGNATURE`` / Tink verification is deferred.)

Endpoint verification handshake
-------------------------------
Before delivering data, Google POSTs ``{"type": "verification"}`` to the endpoint —
once with the Authorization header (must return 2xx) and once without (must return
4xx). Both flow through the standard ``handle()`` pipeline: an authenticated request
passes ``verify_signature`` and ``dispatch`` returns 200; an unauthenticated one fails
``verify_signature`` and the router returns 401.

Fast ack: ``dispatch()`` enqueues a Celery task and returns immediately;
``process_payload()`` does the REST fetch + DB write.

See: https://developers.google.com/health/notifications
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.google import GoogleWebhookNotification
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.health_api.workouts import GoogleHealthApiWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"

# Notification dataTypes that map to a session handler rather than a 24/7 metric.
_SLEEP_DATA_TYPE = "sleep"
_EXERCISE_DATA_TYPE = "exercise"

_SUPPORTED_OPERATIONS = ["UPSERT", "DELETE"]


class GoogleWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Google Health API notify-only events."""

    def __init__(self, data_247: GoogleHealth247Data, workouts: GoogleHealthApiWorkouts) -> None:
        super().__init__("google")
        self.data_247 = data_247
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def extract_user_id(self, payload: Any) -> str | None:
        """healthUserId lives under each notification's ``data`` — pull the first for log correlation."""
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            data = item.get("data") if isinstance(item, dict) else None
            if isinstance(data, dict) and data.get("healthUserId") is not None:
                return str(data["healthUserId"])
        return None

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify the bearer secret Google echoes in the Authorization header."""
        secret_setting = settings.google_webhook_secret
        if not secret_setting:
            log_structured(
                logger,
                "error",
                "GOOGLE_WEBHOOK_SECRET not configured; rejecting webhook",
                provider="google",
                action="webhook_signature_missing_secret",
            )
            return False

        provided = request.headers.get("Authorization", "")
        expected = f"Bearer {secret_setting.get_secret_value()}"
        return self._verify_token(expected, provided)

    def parse_payload(self, body: bytes) -> dict[str, Any] | list[Any]:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            log_structured(
                logger,
                "warning",
                "Google webhook: unparseable body",
                provider="google",
                action="webhook_bad_payload",
                body_len=len(body),
                body_preview=body[:500].decode("utf-8", "replace"),
            )
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        if not isinstance(payload, (dict, list)):
            log_structured(
                logger,
                "warning",
                "Google webhook: unexpected JSON root",
                provider="google",
                action="webhook_bad_payload",
                json_type=type(payload).__name__,
                body_preview=body[:500].decode("utf-8", "replace"),
            )
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        return payload

    def dispatch(self, db: DbSession, payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
        """Ack the verification handshake, or enqueue async processing of a notification batch.

        Google sends the verification handshake as an object (``{"type": "verification"}``)
        and data notifications as a JSON array. ``verify_signature`` has already passed, so an
        authenticated verification handshake simply returns 200.
        """
        if isinstance(payload, dict) and payload.get("type") == "verification":
            log_structured(logger, "info", "Google webhook endpoint verified", provider="google")
            return {"status": "verified"}

        trace_id = str(uuid4())[:8]
        log_structured(
            logger,
            "info",
            "Received Google webhook",
            provider="google",
            trace_id=trace_id,
            notifications=len(payload) if isinstance(payload, list) else 1,
        )

        store_raw_payload(source="webhook", provider="google", payload=payload, trace_id=trace_id)

        task = celery_app.send_task(_PROCESS_PUSH_TASK, args=["google", payload, trace_id], queue="webhook_sync")
        log_structured(
            logger,
            "info",
            "Enqueued Google webhook processing task",
            provider="google",
            trace_id=trace_id,
            task_id=getattr(task, "id", None),
        )
        return {"status": "accepted"}

    def supported_event_types(self) -> list[str]:
        return _SUPPORTED_OPERATIONS

    # ------------------------------------------------------------------
    # Async processing (called by the process_webhook_push Celery task)
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any] | list[Any], trace_id: str) -> dict[str, Any]:
        """Process one notification or a batch; Google sends data notifications as an array."""
        items = payload if isinstance(payload, list) else [payload]
        results: list[dict[str, Any]] = []
        for item in items:
            try:
                results.append(self._process_one(db, item, trace_id))
            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Google webhook notification failed: {e}",
                    extra={"provider": "google", "trace_id": trace_id},
                )
                results.append({"status": "error", "error": str(e)})
        records = sum(int(r.get("records_saved") or 0) for r in results)
        return {"status": "processed", "notifications": len(items), "records_saved": records, "results": results}

    def _process_one(self, db: DbSession, item: Any, trace_id: str) -> dict[str, Any]:
        """Resolve the user, fetch the changed data over its intervals, and persist it."""
        try:
            notification = GoogleWebhookNotification.model_validate(item)
        except (ValidationError, TypeError) as exc:
            log_structured(
                logger,
                "warning",
                "Invalid Google webhook notification",
                provider="google",
                trace_id=trace_id,
                item_keys=sorted(item.keys()) if isinstance(item, dict) else None,
                error=str(exc),
            )
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        data = notification.data

        if data.operation == "DELETE":
            log_structured(
                logger,
                "info",
                "Ignoring Google delete notification",
                provider="google",
                trace_id=trace_id,
                provider_user_id=data.health_user_id,
                data_type=data.data_type,
            )
            return {"status": "ignored", "reason": "delete_operation"}

        connection = self.connection_repo.get_by_provider_user_id(db, "google", data.health_user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Google healthUserId",
                provider="google",
                trace_id=trace_id,
                provider_user_id=data.health_user_id,
                data_type=data.data_type,
            )
            return {"status": "user_not_found", "health_user_id": data.health_user_id, "data_type": data.data_type}

        user_id: UUID = connection.user_id

        window = self._window(data.intervals)
        if window is None:
            log_structured(
                logger,
                "warning",
                "Google notification carried no usable interval; skipping",
                provider="google",
                trace_id=trace_id,
                user_id=str(user_id),
                data_type=data.data_type,
            )
            return {"status": "ignored", "reason": "no_interval", "user_id": str(user_id)}

        start, end = window
        self.connection_repo.update_last_synced_at(db, connection)
        count = self._fetch_and_save(db, user_id, data.data_type, start, end)

        log_structured(
            logger,
            "info",
            "Google webhook notification processed",
            provider="google",
            action="google_webhook_complete",
            trace_id=trace_id,
            user_id=str(user_id),
            provider_user_id=data.health_user_id,
            data_type=data.data_type,
            records_saved=int(count),
        )
        return {
            "status": "processed",
            "data_type": data.data_type,
            "records_saved": int(count),
            "user_id": str(user_id),
        }

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _fetch_and_save(
        self,
        db: DbSession,
        user_id: UUID,
        data_type: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """Route a changed data type to its owning handler and return records saved."""
        if data_type == _EXERCISE_DATA_TYPE:
            return self.workouts.load_data(db, user_id, start_date=start, end_date=end)
        if data_type == _SLEEP_DATA_TYPE:
            return self.data_247.sleep.load_and_save(db, user_id, start, end)
        return int(self.data_247.sync_data_type(db, user_id, data_type, start, end) or 0)

    @staticmethod
    def _window(intervals: Any) -> tuple[datetime, datetime] | None:
        """Span the notification's physical-time intervals into a single [start, end) window."""
        starts: list[datetime] = []
        ends: list[datetime] = []
        for interval in intervals:
            physical = interval.physical_time_interval
            if physical is None:
                continue
            if physical.start_time is not None:
                starts.append(physical.start_time)
            if physical.end_time is not None:
                ends.append(physical.end_time)
        if not starts or not ends:
            return None
        return min(starts), max(ends)
