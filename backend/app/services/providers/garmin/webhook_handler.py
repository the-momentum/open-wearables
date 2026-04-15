"""Garmin webhook handler.

Garmin delivers data in two ways that share the same top-level payload format:

* **PUSH** – the webhook body contains the full inline records.
* **PING** – each item carries a ``callbackURL``; we must fetch the actual
  records from that URL ourselves.

Both modes are handled by a single ``dispatch()`` which detects PING vs PUSH
per data-type by checking whether items contain a ``callbackURL`` field.
"""

import contextlib
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.services.providers.garmin.backfill_state import (
    get_backfill_status,
    get_trace_id,
    mark_type_success,
)
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.handlers.activities import process_activity_notification
from app.services.providers.garmin.handlers.lifecycle import (
    process_deregistrations,
    process_user_permissions,
)
from app.services.providers.garmin.handlers.wellness import process_wellness_items
from app.services.providers.garmin.workouts import GarminWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

WELLNESS_TYPES: list[str] = [
    "dailies",
    "epochs",
    "sleeps",
    "bodyComps",
    "hrv",
    "stressDetails",
    "respiration",
    "pulseox",
    "healthSnapshot",
    "skinTemp",
    "moveiq",
    "mct",
    "userMetrics",
    "bloodPressures",
    "activityDetails",
]

# Celery task path — used with send_task() to avoid a circular import
_TRIGGER_NEXT_TASK = "app.integrations.celery.tasks.garmin_backfill_task.trigger_next_pending_type"


class GarminWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Garmin Health API push/ping events.

    Garmin does not sign request bodies with HMAC; it identifies itself via the
    ``garmin-client-id`` request header.  ``verify_signature`` checks that this
    header is present.
    """

    def __init__(self, garmin_workouts: GarminWorkouts, garmin_247: Garmin247Data) -> None:
        super().__init__("garmin")
        self.garmin_workouts = garmin_workouts
        self.garmin_247 = garmin_247
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        client_id = request.headers.get("garmin-client-id")
        if not client_id:
            log_structured(
                logger,
                "warning",
                "Missing garmin-client-id header",
                provider="garmin",
                action="webhook_signature_invalid",
            )
            return False
        return True

    def parse_payload(self, body: bytes) -> dict[str, Any]:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    def dispatch(self, db: DbSession, payload: dict[str, Any]) -> dict[str, Any]:
        request_trace_id = str(uuid4())[:8]

        item_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in payload.items()}
        garmin_user_ids = list(
            {
                item.get("userId")
                for items in payload.values()
                if isinstance(items, list)
                for item in items
                if isinstance(item, dict) and item.get("userId")
            }
        )
        log_structured(
            logger,
            "info",
            "Received Garmin webhook",
            provider="garmin",
            trace_id=request_trace_id,
            item_counts=item_counts,
            garmin_user_ids=garmin_user_ids,
        )

        store_raw_payload(source="webhook", provider="garmin", payload=payload, trace_id=request_trace_id)

        try:
            errors: list[str] = []
            synced_user_ids: set[UUID] = set()
            users_with_new_success: set[str] = set()

            # --- data processing -----------------------------------------
            act_result = self._process_activities(
                db, payload, errors, synced_user_ids, users_with_new_success, request_trace_id
            )
            well_result = self._process_wellness(
                db, payload, errors, synced_user_ids, users_with_new_success, request_trace_id
            )

            # --- commit + update last_synced_at ---------------------------
            db.commit()

            for uid in synced_user_ids:
                try:
                    connection = self.connection_repo.get_active_connection(db, uid, "garmin")
                    if connection:
                        self.connection_repo.update_last_synced_at(db, connection)
                except Exception as e:
                    log_and_capture_error(
                        e,
                        logger,
                        f"Failed to update last_synced_at for user {uid}",
                        extra={"user_id": str(uid), "provider": "garmin"},
                    )

            # --- build response -------------------------------------------
            response: dict[str, Any] = {
                "processed": act_result["processed_count"],
                "saved": act_result["saved_count"],
                "errors": errors,
                "activities": act_result["details"],
                "wellness": well_result,
                "backfill_chained": [],
            }

            self._process_lifecycle_events(db, payload, response, request_trace_id)
            response["backfill_chained"] = self._chain_backfills(users_with_new_success, request_trace_id)
            return response

        except Exception as exc:
            log_structured(
                logger,
                "error",
                "Unexpected error in Garmin webhook dispatch",
                provider="garmin",
                trace_id=request_trace_id,
                error=str(exc),
                exc_info=True,
            )
            with contextlib.suppress(Exception):
                db.rollback()
            return {
                "processed": 0,
                "saved": 0,
                "errors": [str(exc)],
                "activities": [],
                "wellness": {},
                "backfill_chained": [],
            }

    # ------------------------------------------------------------------
    # Private dispatch helpers
    # ------------------------------------------------------------------

    def _process_activities(
        self,
        db: DbSession,
        payload: dict[str, Any],
        errors: list[str],
        synced_user_ids: set[UUID],
        users_with_new_success: set[str],
        request_trace_id: str,
    ) -> dict[str, Any]:
        processed_count = 0
        saved_count = 0
        details: list[dict[str, Any]] = []

        for notification in payload.get("activities", []):
            result = process_activity_notification(
                db, self.connection_repo, self.garmin_workouts, notification, request_trace_id
            )
            details.append(result)
            status = result.get("status")
            uid_str = result.get("internal_user_id")
            if status in ("saved", "fetched"):
                processed_count += 1
                if status == "saved":
                    saved_count += len(result.get("record_ids", []))
                if uid_str:
                    synced_user_ids.add(UUID(uid_str))
                    if mark_type_success(uid_str, "activities"):
                        users_with_new_success.add(uid_str)
            elif status == "duplicate":
                if uid_str and mark_type_success(uid_str, "activities"):
                    users_with_new_success.add(uid_str)
            elif status in ("error", "user_not_found"):
                errors.append(result.get("error", "Unknown error"))

        return {"processed_count": processed_count, "saved_count": saved_count, "details": details}

    def _process_wellness(
        self,
        db: DbSession,
        payload: dict[str, Any],
        errors: list[str],
        synced_user_ids: set[UUID],
        users_with_new_success: set[str],
        request_trace_id: str,
    ) -> dict[str, Any]:
        wellness_results: dict[str, Any] = {}

        for data_type in WELLNESS_TYPES:
            if not payload.get(data_type):
                continue

            items = payload[data_type]
            log_structured(
                logger,
                "info",
                "Processing wellness notifications",
                provider="garmin",
                trace_id=request_trace_id,
                summary_type=data_type,
                count=len(items),
            )

            result = process_wellness_items(
                db, self.connection_repo, self.garmin_247, data_type, items, errors, synced_user_ids, request_trace_id
            )
            wellness_results[data_type] = {"processed": result["processed"], "saved": result["saved"]}

            for uid_str in result.get("succeeded_users", []):
                if mark_type_success(uid_str, data_type):
                    users_with_new_success.add(uid_str)

        return wellness_results

    def _process_lifecycle_events(
        self,
        db: DbSession,
        payload: dict[str, Any],
        response: dict[str, Any],
        request_trace_id: str,
    ) -> None:
        if "userPermissionsChange" in payload:
            try:
                response["userPermissionsChange"] = process_user_permissions(
                    db, self.connection_repo, payload["userPermissionsChange"], request_trace_id
                )
            except Exception as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to process permission changes",
                    provider="garmin",
                    trace_id=request_trace_id,
                    error=str(e),
                )
                response["userPermissionsChange"] = {"updated": 0, "errors": [str(e)]}

        if "deregistrations" in payload:
            try:
                response["deregistrations"] = process_deregistrations(
                    db, self.connection_repo, payload["deregistrations"], request_trace_id
                )
            except Exception as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to process deregistrations",
                    provider="garmin",
                    trace_id=request_trace_id,
                    error=str(e),
                )
                response["deregistrations"] = {"revoked": 0, "errors": [str(e)]}

    def _chain_backfills(self, users_with_new_success: set[str], request_trace_id: str) -> list[str]:
        backfill_triggered: list[str] = []
        for user_id_str in users_with_new_success:
            backfill_status = get_backfill_status(user_id_str)
            if backfill_status["overall_status"] in ("in_progress", "retry_in_progress"):
                trace_id = get_trace_id(user_id_str) or request_trace_id
                log_structured(
                    logger,
                    "info",
                    "Triggering next backfill",
                    provider="garmin",
                    trace_id=trace_id,
                    user_id=user_id_str,
                    current_window=backfill_status["current_window"],
                    total_windows=backfill_status["total_windows"],
                )
                celery_app.send_task(_TRIGGER_NEXT_TASK, args=[user_id_str])
                backfill_triggered.append(user_id_str)
        return backfill_triggered

    def supported_event_types(self) -> list[str]:
        return ["activities", *WELLNESS_TYPES, "userPermissionsChange", "deregistrations"]
