"""Strava webhook handler.

Strava sends notify-only webhooks: a lightweight payload containing the athlete
ID, object ID, and aspect type. Full activity data must be fetched via
GET /activities/{id}.

Authenticity
------------
  X-Strava-Signature can't be verified (Strava doesn't expose its signing key), so only its
  timestamp is checked, against replays. A delete or a deauthorization is confirmed in the
  Strava API with the athlete's token before anything is removed.

Challenge verification
-----------------------
  On subscription creation, Strava GETs the callback URL with:
    hub.mode=subscribe, hub.challenge=<random>, hub.verify_token=<our token>
  We verify the token and echo back {"hub.challenge": <value>}.

Delivery model
--------------
  ``dispatch()`` acknowledges the event immediately (returns 200 quickly) and
  enqueues a Celery task. ``process_payload()`` does the actual Strava API
  fetch and DB write, called by the shared ``process_webhook_push`` task.

Supported event types
---------------------
  activity create / update / delete, and athlete deauthorization (an athlete update
  with updates == {"authorized": "false"})

See: https://developers.strava.com/docs/webhooks/
"""

import json
import time
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.constants.celery_tasks import CeleryQueue, CeleryTask
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.schemas.providers.strava import StravaWebhookEvent
from app.services.event_record_service import event_record_service
from app.services.providers.strava.workouts import StravaWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.exceptions import (
    InvalidInputError,
    PermissionDeniedError,
    ProviderError,
    ReauthRequiredError,
    is_unique_violation,
)
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


class StravaWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Strava notify-only events."""

    user_id_field = "owner_id"

    def __init__(self, workouts: StravaWorkouts) -> None:
        super().__init__("strava")
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Check the X-Strava-Signature timestamp only; its HMAC can't be verified (see the module docstring)."""
        header = request.headers.get("X-Strava-Signature", "")
        if not header:
            return False

        try:
            parts = dict(p.split("=", 1) for p in header.split(","))
            timestamp = int(parts["t"])
        except (KeyError, ValueError):
            return False

        if abs(time.time() - timestamp) > settings.strava_webhook_signature_tolerance_seconds:
            logger.warning(
                "Strava webhook timestamp outside tolerance window",
                provider="strava",
                action="webhook_signature_expired",
            )
            return False

        return True

    def parse_payload(self, body: bytes) -> StravaWebhookEvent:
        try:
            data = json.loads(body)
            return StravaWebhookEvent(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise InvalidInputError("Invalid JSON body") from exc
        except (ValidationError, TypeError) as exc:
            raise InvalidInputError(f"Invalid payload: {exc}") from exc

    def dispatch(self, db: DbSession, payload: StravaWebhookEvent) -> dict[str, Any]:
        """Store raw payload and enqueue async processing. Returns 200 immediately."""
        trace_id = str(uuid4())[:8]
        raw = payload.model_dump()

        logger.info(
            "Received Strava webhook event",
            provider="strava",
            trace_id=trace_id,
            object_type=payload.object_type,
            aspect_type=payload.aspect_type,
            object_id=payload.object_id,
            owner_id=payload.owner_id,
        )

        store_raw_payload(source="webhook", provider="strava", payload=raw, trace_id=trace_id)

        task = celery_app.send_task(
            CeleryTask.PROCESS_WEBHOOK_PUSH, args=["strava", raw, trace_id], queue=CeleryQueue.WEBHOOK_SYNC
        )
        logger.info(
            "Enqueued Strava webhook processing task",
            provider="strava",
            trace_id=trace_id,
            task_id=getattr(task, "id", None),
        )

        return {"status": "accepted"}

    def handle_challenge(self, request: Request) -> dict[str, Any]:
        """Handle Strava GET subscription verification (hub.challenge)."""
        hub_mode = request.query_params.get("hub.mode", "")
        hub_challenge = request.query_params.get("hub.challenge", "")
        hub_verify_token = request.query_params.get("hub.verify_token", "")

        if hub_mode != "subscribe":
            raise InvalidInputError("Invalid hub.mode")

        expected_token = (
            settings.strava_webhook_verify_token.get_secret_value() if settings.strava_webhook_verify_token else None
        )
        if not expected_token or not hub_verify_token or not self._verify_token(expected_token, hub_verify_token):
            logger.warning(
                "Invalid Strava webhook verify token",
                provider="strava",
                action="webhook_challenge_failed",
            )
            raise PermissionDeniedError("Invalid verify token")

        logger.info(
            "Strava webhook subscription verified",
            provider="strava",
            action="webhook_challenge_accepted",
        )
        return {"hub.challenge": hub_challenge}

    def supported_event_types(self) -> list[str]:
        return ["activity_create", "activity_update", "activity_delete", "athlete_update"]

    def _handle_activity_delete(self, db: DbSession, user_id: UUID, activity_id: int, trace_id: str) -> dict[str, Any]:
        # Nothing to delete: a forged event must not spend the app-wide Strava rate limit
        if not event_record_service.crud.get_by_external_ids(db, user_id, [str(activity_id)], provider="strava"):
            logger.info(
                "Strava activity not stored, ignoring delete event",
                provider="strava",
                trace_id=trace_id,
                action="webhook_activity_delete_not_stored",
                activity_id=activity_id,
                user_id=str(user_id),
            )
            return {"status": "ignored", "reason": "activity_not_stored", "activity_id": activity_id}

        try:
            self.workouts.get_workout_detail_from_api(db, user_id, str(activity_id))
        except ProviderError as exc:
            if exc.upstream_status != 404:
                raise
        else:
            logger.warning(
                "Strava still has the activity, ignoring delete event",
                provider="strava",
                trace_id=trace_id,
                action="webhook_activity_delete_unconfirmed",
                activity_id=activity_id,
                user_id=str(user_id),
            )
            return {"status": "ignored", "reason": "activity_still_exists", "activity_id": activity_id}

        deleted = event_record_service.crud.delete_by_external_id(db, user_id, str(activity_id), provider="strava")
        logger.info(
            "Strava activity deleted",
            provider="strava",
            trace_id=trace_id,
            action="webhook_activity_deleted",
            activity_id=activity_id,
            user_id=str(user_id),
            records_deleted=deleted,
        )
        return {"status": "deleted", "activity_id": activity_id, "records_deleted": deleted}

    @staticmethod
    def _is_deauthorization(event: StravaWebhookEvent) -> bool:
        """Strava reports a deauthorization as an athlete update with authorized == "false"."""
        return (
            event.object_type == "athlete"
            and event.aspect_type == "update"
            and event.updates.get("authorized") in ("false", False)
        )

    def _handle_athlete_deauthorize(self, db: DbSession, owner_id: int, trace_id: str) -> dict[str, Any]:
        connection = self.connection_repo.get_by_provider_user_id(db, "strava", str(owner_id))
        if not connection:
            logger.warning(
                "No connection found for deauthorizing Strava athlete",
                provider="strava",
                trace_id=trace_id,
                action="webhook_deauth_no_connection",
                strava_athlete_id=owner_id,
            )
            return {"status": "user_not_found", "strava_athlete_id": owner_id}

        user_id = connection.user_id
        # Strava rejects both tokens of a deauthorized grant; we revoke, so the reason is "deregistration"
        try:
            self.workouts.get_athlete_from_api(db, user_id, revoke_on_failure=False)
        except ReauthRequiredError:
            self.workouts.oauth.revoke_connection(db, user_id, reason="deregistration")
            return {"status": "deauthorized", "strava_athlete_id": owner_id}

        logger.warning(
            "Strava still authorizes the athlete, ignoring deauthorization event",
            provider="strava",
            trace_id=trace_id,
            action="webhook_athlete_deauth_unconfirmed",
            strava_athlete_id=owner_id,
            user_id=str(user_id),
        )
        return {"status": "ignored", "reason": "athlete_still_authorized", "strava_athlete_id": owner_id}

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process a Strava notify-only payload.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        """
        try:
            event = StravaWebhookEvent(**payload)
        except (ValidationError, TypeError) as exc:
            logger.error(
                "Invalid Strava webhook payload",
                exc_info=exc,
                provider="strava",
                trace_id=trace_id,
                action="webhook_invalid_payload",
            )
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        object_type = event.object_type
        aspect_type = event.aspect_type
        object_id = event.object_id
        owner_id = event.owner_id

        if self._is_deauthorization(event):
            return self._handle_athlete_deauthorize(db, owner_id, trace_id)

        if object_type != "activity":
            logger.info(
                "Ignoring non-activity Strava event",
                provider="strava",
                trace_id=trace_id,
                object_type=object_type,
            )
            return {"status": "ignored", "reason": f"object_type:{object_type}"}

        connection = self.connection_repo.get_by_provider_user_id(db, "strava", str(owner_id))
        if not connection:
            logger.warning(
                "No connection found for Strava athlete",
                provider="strava",
                trace_id=trace_id,
                action="webhook_no_connection",
                strava_athlete_id=owner_id,
            )
            return {"status": "user_not_found", "strava_athlete_id": owner_id}

        user_id: UUID = connection.user_id

        result = self._handle_activity_event(db, aspect_type, user_id, object_id, owner_id, trace_id)
        if aspect_type in ("create", "update") and result.get("status") != "error":
            self.connection_repo.update_last_synced_at(db, connection)
        return result

    def _handle_activity_event(
        self,
        db: DbSession,
        aspect_type: str,
        user_id: UUID,
        object_id: int,
        owner_id: int,
        trace_id: str,
    ) -> dict[str, Any]:
        """Apply an activity create/update/delete for a resolved user."""
        if aspect_type == "delete":
            return self._handle_activity_delete(db, user_id, object_id, trace_id)

        if aspect_type not in ("create", "update"):
            return {"status": "ignored", "reason": f"aspect_type:{aspect_type}", "user_id": str(user_id)}

        logger.info(
            "Processing Strava webhook activity",
            provider="strava",
            trace_id=trace_id,
            user_id=str(user_id),
            strava_athlete_id=owner_id,
            activity_id=object_id,
            aspect_type=aspect_type,
        )

        try:
            activity_data = self.workouts.get_workout_detail_from_api(db, user_id, str(object_id))
            if not activity_data:
                logger.warning(
                    "No data returned for Strava activity",
                    provider="strava",
                    trace_id=trace_id,
                    action="webhook_no_activity_data",
                    activity_id=object_id,
                    user_id=str(user_id),
                )
                return {
                    "status": "warning",
                    "reason": "no_activity_data",
                    "activity_id": object_id,
                    "user_id": str(user_id),
                }

            activity = StravaActivityJSON(**activity_data)
            created_ids = self.workouts.process_push_activity(db=db, activity=activity, user_id=user_id)

            logger.info(
                "Strava activity saved",
                provider="strava",
                trace_id=trace_id,
                action="webhook_activity_saved",
                activity_id=object_id,
                user_id=str(user_id),
                record_count=len(created_ids),
            )
            return {
                "status": "processed",
                "activity_id": object_id,
                "records_saved": len(created_ids),
                "user_id": str(user_id),
            }

        except IntegrityError as exc:
            db.rollback()
            if not is_unique_violation(exc):
                raise
            logger.info(
                "Strava activity already exists, skipping",
                provider="strava",
                trace_id=trace_id,
                action="webhook_duplicate_activity",
                activity_id=object_id,
                user_id=str(user_id),
            )
            return {
                "status": "ignored",
                "reason": "duplicate_activity",
                "activity_id": object_id,
                "user_id": str(user_id),
            }

        except ValidationError as exc:
            logger.error(
                "Failed to parse Strava activity",
                exc_info=exc,
                provider="strava",
                trace_id=trace_id,
                action="webhook_validation_error",
                activity_id=object_id,
                user_id=str(user_id),
                error=str(exc),
            )
            return {"status": "error", "error": f"validation_error: {exc}", "user_id": str(user_id)}

        except Exception as exc:
            logger.error(
                "Error processing Strava activity",
                exc_info=exc,
                provider="strava",
                trace_id=trace_id,
                action="webhook_processing_error",
                activity_id=object_id,
                user_id=str(user_id),
                error=str(exc),
            )
            raise
