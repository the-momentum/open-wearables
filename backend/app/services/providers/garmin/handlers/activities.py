"""Garmin activity webhook handler.

Processes a single activity notification — either PUSH (inline data) or
PING (callbackURL to fetch from Garmin).
"""

import logging
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.providers.garmin import ActivityJSON as GarminActivityJSON
from app.services.providers.garmin.backfill_state import get_trace_id
from app.services.providers.garmin.workouts import GarminWorkouts
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def process_activity_notification(
    db: DbSession,
    connection_repo: UserConnectionRepository,
    garmin_workouts: GarminWorkouts,
    notification: dict[str, Any],
    request_trace_id: str,
) -> dict[str, Any]:
    """Process a single Garmin activity notification (PUSH inline or PING callback)."""
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
        return {**base_result, "status": "user_not_found", "error": "Missing userId in activity notification"}

    connection = connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
    if not connection:
        log_structured(
            logger,
            "warning",
            "No connection found for Garmin user",
            provider="garmin",
            trace_id=request_trace_id,
            garmin_user_id=garmin_user_id,
        )
        return {**base_result, "status": "user_not_found", "error": f"User {garmin_user_id} not connected"}

    internal_user_id = connection.user_id
    trace_id = get_trace_id(internal_user_id) or request_trace_id

    if "callbackURL" in notification:
        # PING: fetch activities from the callback URL (no DB save at this stage)
        callback_url = notification["callbackURL"]
        log_structured(
            logger,
            "info",
            "Activity callback URL received",
            provider="garmin",
            trace_id=trace_id,
            garmin_user_id=garmin_user_id,
            internal_user_id=str(internal_user_id),
        )
        try:
            response = httpx.get(callback_url, timeout=30.0)
            response.raise_for_status()
            activities_data = response.json()
            activities_count = len(activities_data) if isinstance(activities_data, list) else 1
            log_structured(
                logger,
                "info",
                "Fetched activities from callback",
                provider="garmin",
                trace_id=trace_id,
                internal_user_id=str(internal_user_id),
                activities_count=activities_count,
            )
            return {**base_result, "internal_user_id": str(internal_user_id), "status": "fetched"}
        except httpx.HTTPError as e:
            log_structured(
                logger,
                "error",
                "Failed to fetch activity data from callback URL",
                provider="garmin",
                trace_id=trace_id,
                error=str(e),
            )
            return {**base_result, "status": "error", "error": f"HTTP error: {e}"}

    # PUSH: parse and save inline data
    log_structured(
        logger,
        "info",
        "New Garmin activity received",
        provider="garmin",
        trace_id=trace_id,
        activity_name=activity_name,
        activity_type=activity_type,
        activity_id=activity_id,
        garmin_user_id=garmin_user_id,
        user_id=str(internal_user_id),
    )
    try:
        activity = GarminActivityJSON(**notification)
    except ValidationError as e:
        log_structured(
            logger,
            "error",
            "Failed to parse activity data",
            provider="garmin",
            trace_id=trace_id,
            activity_id=activity_id,
            error=str(e),
        )
        return {**base_result, "status": "validation_error", "error": f"Invalid activity data: {e}"}

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
            trace_id=request_trace_id,
            activity_id=activity_id,
        )
        return {**base_result, "status": "duplicate"}

    log_structured(
        logger,
        "info",
        "Saved activity",
        provider="garmin",
        trace_id=trace_id,
        activity_id=activity_id,
        record_ids=[str(rid) for rid in created_ids],
    )
    return {
        **base_result,
        "internal_user_id": str(internal_user_id),
        "record_ids": [str(rid) for rid in created_ids],
        "status": "saved",
    }
