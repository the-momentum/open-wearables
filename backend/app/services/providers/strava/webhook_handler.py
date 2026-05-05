"""Strava webhook handler.

Strava sends notify-only webhooks: a lightweight payload containing the athlete
ID, object ID, and aspect type. Full activity data must be fetched via
GET /activities/{id}.

Signature scheme
----------------
  Header   : X-Strava-Signature: t=<unix_ts>,v1=<hex_digest>
  Message  : {t}.{raw_request_body}
  Algorithm: HMAC-SHA256(strava_client_secret, message)
  Tolerance: settings.strava_webhook_signature_tolerance_seconds (default 300)

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
  activity create / update / delete + athlete deauthorize (delete)

See: https://developers.strava.com/docs/webhooks/
"""

import json
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from celery import current_app as celery_app
from fastapi import HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.schemas.providers.strava import StravaWebhookEvent
from app.services.providers.strava.workouts import StravaWorkouts
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROCESS_PUSH_TASK = "app.integrations.celery.tasks.webhook_push_task.process_webhook_push"


class StravaWebhookHandler(BaseWebhookHandler):
    """Webhook handler for Strava notify-only events."""

    def __init__(self, workouts: StravaWorkouts) -> None:
        super().__init__("strava")
        self.workouts = workouts
        self.connection_repo = UserConnectionRepository()

    # ------------------------------------------------------------------
    # BaseWebhookHandler interface
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify X-Strava-Signature using HMAC-SHA256.

        Header format: ``t=<unix_ts>,v1=<hex_digest>``
        Signed payload: ``{t}.{raw_body}``
        Signing key: ``strava_client_secret`` (the shared signing secret).
        """
        header = request.headers.get("X-Strava-Signature", "")
        if not header:
            log_structured(
                logger,
                "warning",
                "Missing X-Strava-Signature header",
                provider="strava",
                action="webhook_signature_missing",
            )
            return False

        try:
            parts = dict(p.split("=", 1) for p in header.split(","))
            timestamp = parts["t"]
            signature = parts["v1"]
        except (KeyError, ValueError):
            log_structured(
                logger,
                "warning",
                "Malformed X-Strava-Signature header",
                provider="strava",
                action="webhook_signature_malformed",
                header=header,
            )
            return False

        if abs(time.time() - int(timestamp)) > settings.strava_webhook_signature_tolerance_seconds:
            log_structured(
                logger,
                "warning",
                "Strava webhook timestamp outside tolerance window",
                provider="strava",
                action="webhook_signature_expired",
            )
            return False

        # Strava signs with the app's client_secret (the "shared signing secret")
        secret = settings.strava_client_secret.get_secret_value()  # type: ignore[union-attr]
        return self._verify_hmac_sha256(secret, body, signature, prefix=f"{timestamp}.".encode())

    def parse_payload(self, body: bytes) -> StravaWebhookEvent:
        try:
            data = json.loads(body)
            return StravaWebhookEvent(**data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        except (ValidationError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc

    def dispatch(self, db: DbSession, payload: StravaWebhookEvent) -> dict[str, Any]:
        """Store raw payload and enqueue async processing. Returns 200 immediately."""
        trace_id = str(uuid4())[:8]
        raw = payload.model_dump()

        log_structured(
            logger,
            "info",
            "Received Strava webhook event",
            provider="strava",
            trace_id=trace_id,
            object_type=payload.object_type,
            aspect_type=payload.aspect_type,
            object_id=payload.object_id,
            owner_id=payload.owner_id,
        )

        store_raw_payload(source="webhook", provider="strava", payload=raw, trace_id=trace_id)

        task = celery_app.send_task(_PROCESS_PUSH_TASK, args=["strava", raw, trace_id], queue="webhook_sync")
        log_structured(
            logger,
            "info",
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
            raise HTTPException(status_code=400, detail="Invalid hub.mode")

        expected_token = (
            settings.strava_webhook_verify_token.get_secret_value() if settings.strava_webhook_verify_token else None
        )
        if not expected_token or not hub_verify_token or not self._verify_token(expected_token, hub_verify_token):
            log_structured(
                logger,
                "warning",
                "Invalid Strava webhook verify token",
                provider="strava",
                action="webhook_challenge_failed",
            )
            raise HTTPException(status_code=403, detail="Invalid verify token")

        log_structured(
            logger,
            "info",
            "Strava webhook subscription verified",
            provider="strava",
            action="webhook_challenge_accepted",
        )
        return {"hub.challenge": hub_challenge}

    def supported_event_types(self) -> list[str]:
        return ["activity_create", "activity_update", "activity_delete", "athlete_delete"]

    # ------------------------------------------------------------------
    # Async processing (called by Celery task)
    # ------------------------------------------------------------------

    def process_payload(self, db: DbSession, payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
        """Process a Strava notify-only payload.

        Called by the ``process_webhook_push`` Celery task with its own DB session.
        """
        try:
            event = StravaWebhookEvent(**payload)
        except (ValidationError, TypeError) as exc:
            return {"status": "error", "error": f"Invalid payload: {exc}"}

        object_type = event.object_type
        aspect_type = event.aspect_type
        object_id = event.object_id
        owner_id = event.owner_id

        if object_type != "activity":
            log_structured(
                logger,
                "info",
                "Ignoring non-activity Strava event",
                provider="strava",
                trace_id=trace_id,
                object_type=object_type,
            )
            return {"status": "ignored", "reason": f"object_type:{object_type}"}

        if aspect_type not in ("create", "update"):
            log_structured(
                logger,
                "info",
                "Ignoring Strava activity event",
                provider="strava",
                trace_id=trace_id,
                aspect_type=aspect_type,
                object_id=object_id,
            )
            return {"status": "ignored", "reason": f"aspect_type:{aspect_type}"}

        connection = self.connection_repo.get_by_provider_user_id(db, "strava", str(owner_id))
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Strava athlete",
                provider="strava",
                trace_id=trace_id,
                action="webhook_no_connection",
                strava_athlete_id=owner_id,
            )
            return {"status": "user_not_found", "strava_athlete_id": owner_id}

        user_id: UUID = connection.user_id

        log_structured(
            logger,
            "info",
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
                log_structured(
                    logger,
                    "warning",
                    "No data returned for Strava activity",
                    provider="strava",
                    trace_id=trace_id,
                    action="webhook_no_activity_data",
                    activity_id=object_id,
                    user_id=str(user_id),
                )
                return {"status": "warning", "reason": "no_activity_data", "activity_id": object_id}

            activity = StravaActivityJSON(**activity_data)
            created_ids = self.workouts.process_push_activity(db=db, activity=activity, user_id=user_id)

            log_structured(
                logger,
                "info",
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
            }

        except IntegrityError:
            db.rollback()
            log_structured(
                logger,
                "info",
                "Strava activity already exists, skipping",
                provider="strava",
                trace_id=trace_id,
                action="webhook_duplicate_activity",
                activity_id=object_id,
                user_id=str(user_id),
            )
            return {"status": "ignored", "reason": "duplicate_activity", "activity_id": object_id}

        except ValidationError as exc:
            log_structured(
                logger,
                "error",
                "Failed to parse Strava activity",
                provider="strava",
                trace_id=trace_id,
                action="webhook_validation_error",
                activity_id=object_id,
                user_id=str(user_id),
                error=str(exc),
            )
            return {"status": "error", "error": f"validation_error: {exc}"}

        except Exception as exc:
            log_structured(
                logger,
                "error",
                "Error processing Strava activity",
                provider="strava",
                trace_id=trace_id,
                action="webhook_processing_error",
                activity_id=object_id,
                user_id=str(user_id),
                error=str(exc),
            )
            raise
