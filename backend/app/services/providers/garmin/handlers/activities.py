"""Garmin activity webhook handler.

Processes a single activity notification — either PUSH (inline data) or
PING (callbackURL to fetch from Garmin).
"""

import logging
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.garmin import ActivityJSON as GarminActivityJSON
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services.providers.garmin.backfill_state import get_trace_id
from app.services.providers.garmin.workouts import GarminWorkouts
from app.services.sync_status_service import completed, new_run_id
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def process_activity_notification(
    db: DbSession,
    connection_repo: UserConnectionRepository,
    garmin_workouts: GarminWorkouts,
    notification: dict[str, Any],
    request_trace_id: str,
) -> list[dict[str, Any]]:
    """Process a single Garmin activity notification for all linked OW profiles.

    Returns one result dict per linked profile.  The first connection is treated
    as primary (WEBHOOK source); any additional profiles sharing the same Garmin
    account receive LINKED_ACCOUNT events.
    """
    garmin_user_id: str | None = notification.get("userId")
    activity_id = notification.get("activityId")
    activity_name = notification.get("activityName")
    activity_type = notification.get("activityType")

    base_result: dict[str, Any] = {
        "activity_id": activity_id,
        "name": activity_name,
        "type": activity_type,
        "garmin_user_id": garmin_user_id,
    }

    if not garmin_user_id:
        return [{**base_result, "status": "user_not_found", "error": "Missing userId in activity notification"}]

    connections = connection_repo.get_all_by_provider_user_id(db, "garmin", garmin_user_id)
    if not connections:
        log_structured(
            logger,
            "warning",
            "No connection found for Garmin user",
            provider="garmin",
            trace_id=request_trace_id,
            garmin_user_id=garmin_user_id,
        )
        return [{**base_result, "status": "user_not_found", "error": f"User {garmin_user_id} not connected"}]

    if "callbackURL" in notification:
        # PING not supported; Garmin must be configured for PUSH-only delivery.
        return [{**base_result, "status": "skipped"} for _ in connections]

    # Parse activity data once — reused for every linked profile.
    try:
        activity = GarminActivityJSON(**notification)
    except ValidationError as e:
        log_structured(
            logger,
            "error",
            "Failed to parse activity data",
            provider="garmin",
            trace_id=request_trace_id,
            activity_id=activity_id,
            error=str(e),
        )
        err_result = {**base_result, "status": "validation_error", "error": f"Invalid activity data: {e}"}
        return [err_result for _ in connections]

    primary_user_id: UUID = connections[0].user_id
    results: list[dict[str, Any]] = []

    for i, connection in enumerate(connections):
        internal_user_id = connection.user_id
        trace_id = get_trace_id(internal_user_id) or request_trace_id
        is_primary = i == 0
        sync_source = SyncSource.WEBHOOK if is_primary else SyncSource.LINKED_ACCOUNT

        log_structured(
            logger,
            "info" if is_primary else "debug",
            "New Garmin activity received",
            provider="garmin",
            trace_id=trace_id,
            activity_name=activity_name,
            activity_type=activity_type,
            activity_id=activity_id,
            garmin_user_id=garmin_user_id,
            user_id=str(internal_user_id),
            is_primary=is_primary,
        )
        try:
            created_ids = garmin_workouts.process_push_activities(
                db=db,
                activities=[activity],
                user_id=internal_user_id,
            )
        except IntegrityError:
            db.rollback()
            log_structured(
                logger,
                "info",
                "Activity already exists, skipping",
                provider="garmin",
                trace_id=trace_id,
                activity_id=activity_id,
                user_id=str(internal_user_id),
            )
            results.append({**base_result, "internal_user_id": str(internal_user_id), "status": "duplicate"})
            continue

        log_structured(
            logger,
            "info" if is_primary else "debug",
            "Saved activity",
            provider="garmin",
            trace_id=trace_id,
            activity_id=activity_id,
            user_id=str(internal_user_id),
            record_ids=[str(rid) for rid in created_ids],
        )
        completed(
            internal_user_id,
            "garmin",
            sync_source,
            run_id=new_run_id(prefix=f"garmin_webhook_activity_{activity_id}"),
            status=SyncStatus.SUCCESS,
            message=f"Garmin activity received: {activity_name}",
            items_processed=len(created_ids),
            primary_user_id=None if is_primary else primary_user_id,
            metadata={"trace_id": trace_id, "activity_id": activity_id, "activity_type": activity_type},
        )
        results.append(
            {
                **base_result,
                "internal_user_id": str(internal_user_id),
                "record_ids": [str(rid) for rid in created_ids],
                "status": "saved",
            }
        )

    return results
