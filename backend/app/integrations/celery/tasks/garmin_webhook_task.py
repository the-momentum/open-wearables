"""Celery tasks for processing Garmin push/ping notifications."""

from logging import getLogger
from typing import Any, cast
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import DbSession, SessionLocal
from app.integrations.celery.tasks.garmin_backfill_task import (
    get_backfill_status,
    get_trace_id,
    mark_type_success,
    trigger_next_pending_type,
)
from app.repositories import UserConnectionRepository
from app.schemas.providers.garmin import ActivityJSON as GarminActivityJSON
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.workouts import GarminWorkouts
from app.utils.structured_logging import log_structured
from celery import Task, shared_task

logger = getLogger(__name__)

GARMIN_SYNC_QUEUE = "garmin_sync"


def _process_wellness_notification(
    db: DbSession,
    summary_type: str,
    notifications: list[dict[str, Any]],
    garmin_247: Garmin247Data,
    request_trace_id: str,
) -> dict[str, Any]:
    """Process wellness data notifications (dailies, epochs, sleeps, etc.).

    Args:
        db: Database session
        summary_type: Type of data ("dailies", "epochs", "sleeps", etc.)
        notifications: List of notification items from webhook payload
        garmin_247: Garmin 247 data service instance
        request_trace_id: Trace ID for this webhook request (backfill or request-level)

    Returns:
        Dict with processing results
    """
    results: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "errors": [],
        "items": [],
        "new_success_users": [],
    }

    user_connection_repo = UserConnectionRepository()

    for notification in notifications:
        garmin_user_id = notification.get("userId")
        callback_url = notification.get("callbackURL")

        if not callback_url:
            log_structured(
                logger,
                "warning",
                "No callback URL in notification",
                provider="garmin",
                trace_id=request_trace_id,
                summary_type=summary_type,
                garmin_user_id=garmin_user_id,
            )
            continue

        # Find internal user
        if not garmin_user_id:
            log_structured(
                logger,
                "warning",
                "No user ID in notification",
                provider="garmin",
                trace_id=request_trace_id,
                summary_type=summary_type,
            )
            continue
        connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Garmin user",
                provider="garmin",
                trace_id=request_trace_id,
                garmin_user_id=garmin_user_id,
            )
            results["errors"].append(f"User {garmin_user_id} not connected")
            continue

        user_id: UUID = connection.user_id
        # Use backfill trace_id if active, otherwise the request-level trace_id
        trace_id = get_trace_id(user_id) or request_trace_id

        log_structured(
            logger,
            "info",
            "Processing wellness data",
            provider="garmin",
            trace_id=trace_id,
            summary_type=summary_type,
            user_id=str(user_id),
            garmin_user_id=garmin_user_id,
        )

        try:
            # Fetch data from callback URL
            response = httpx.get(callback_url, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                data = [data]

            log_structured(
                logger,
                "info",
                "Fetched wellness items",
                provider="garmin",
                trace_id=trace_id,
                summary_type=summary_type,
                item_count=len(data),
                user_id=str(user_id),
            )

            # Batch process all items with minimal DB round-trips
            count = garmin_247.process_items_batch(db, user_id, summary_type, data)

            results["processed"] += len(data)
            results["saved"] += count
            results["items"].append(
                {
                    "garmin_user_id": garmin_user_id,
                    "internal_user_id": str(user_id),
                    "type": summary_type,
                    "fetched": len(data),
                    "saved": count,
                }
            )

            log_structured(
                logger,
                "info",
                "Saved wellness data",
                provider="garmin",
                trace_id=trace_id,
                summary_type=summary_type,
                saved=count,
                user_id=str(user_id),
            )

            # Mark type as success for backfill tracking
            if count > 0 and mark_type_success(str(user_id), summary_type):
                results["new_success_users"].append(str(user_id))

        except httpx.HTTPError as e:
            log_structured(
                logger,
                "error",
                "HTTP error fetching wellness data",
                provider="garmin",
                trace_id=trace_id,
                summary_type=summary_type,
                error=str(e),
            )
            results["errors"].append(f"HTTP error: {str(e)}")
        except Exception as e:
            log_structured(
                logger,
                "error",
                "Error processing wellness notification",
                provider="garmin",
                trace_id=trace_id,
                summary_type=summary_type,
                error=str(e),
            )
            results["errors"].append(f"Error: {str(e)}")

    return results


def _process_user_permissions(
    db: DbSession,
    permissions_list: list[dict[str, Any]],
    trace_id: str,
) -> dict[str, Any]:
    """Process userPermissions webhook entries.

    Called when a user changes their data sharing permissions on Garmin Connect.
    Updates the scope column on the matching user_connection.
    """
    results: dict[str, Any] = {"updated": 0, "errors": []}

    if not isinstance(permissions_list, list):
        return {"updated": 0, "errors": ["Invalid userPermissions payload format"]}

    user_connection_repo = UserConnectionRepository()

    for entry in permissions_list:
        if not isinstance(entry, dict):
            results["errors"].append("Invalid userPermissions entry format")
            continue

        garmin_user_id = entry.get("userId")
        if not garmin_user_id:
            results["errors"].append("Missing userId in userPermissions entry")
            continue

        connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Garmin user (userPermissions)",
                provider="garmin",
                trace_id=trace_id,
                garmin_user_id=garmin_user_id,
            )
            results["errors"].append(f"User {garmin_user_id} not connected")
            continue

        # permissions is a flat list of permitted permission names:
        # ["ACTIVITY_EXPORT", "HEALTH_EXPORT", ...]
        permissions = entry.get("permissions", [])
        new_scope = " ".join(sorted(permissions)) if permissions else None
        old_scope = connection.scope

        user_connection_repo.update_scope(db, connection, new_scope)

        log_structured(
            logger,
            "info",
            "Updated user permissions scope",
            provider="garmin",
            trace_id=trace_id,
            garmin_user_id=garmin_user_id,
            user_id=str(connection.user_id),
            old_scope=old_scope,
            new_scope=new_scope,
        )
        results["updated"] += 1

    return results


def _process_deregistrations(
    db: DbSession,
    deregistrations_list: list[dict[str, Any]],
    trace_id: str,
) -> dict[str, Any]:
    """Process deregistration webhook entries.

    Called when a user removes the app from Garmin Connect.
    Marks the matching user_connection as revoked.
    """
    results: dict[str, Any] = {"revoked": 0, "errors": []}

    if not isinstance(deregistrations_list, list):
        return {"revoked": 0, "errors": ["Invalid deregistrations payload format"]}

    user_connection_repo = UserConnectionRepository()

    for entry in deregistrations_list:
        if not isinstance(entry, dict):
            results["errors"].append("Invalid deregistrations entry format")
            continue

        garmin_user_id = entry.get("userId")
        if not garmin_user_id:
            results["errors"].append("Missing userId in deregistrations entry")
            continue

        connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Garmin user (deregistration)",
                provider="garmin",
                trace_id=trace_id,
                garmin_user_id=garmin_user_id,
            )
            results["errors"].append(f"User {garmin_user_id} not connected")
            continue

        user_connection_repo.mark_as_revoked(db, connection)

        log_structured(
            logger,
            "info",
            "Revoked connection via deregistration webhook",
            provider="garmin",
            trace_id=trace_id,
            garmin_user_id=garmin_user_id,
            user_id=str(connection.user_id),
        )
        results["revoked"] += 1

    return results


@shared_task(
    bind=True,
    queue=GARMIN_SYNC_QUEUE,
    max_retries=2,
    default_retry_delay=60,  # retry after 1 minute if it fails
    acks_late=True,  # only acknowledge the task after it completes successfully
    reject_on_worker_lost=True,  # re-queue the task if the worker processing it dies
)
def process_ping(self: Task, payload: dict[str, Any], request_trace_id: str) -> dict[str, Any]:
    """Process a Garmin PING webhook payload asynchronously as a Celery task.

    Args:
        payload: The JSON payload from the Garmin PING webhook.
        request_trace_id: Trace ID from the incoming webhook request for logging correlation.
    """
    db = SessionLocal()
    try:
        # Process different summary types
        processed_count = 0
        errors: list[str] = []
        processed_activities: list[dict] = []
        synced_user_ids: set[UUID] = set()

        user_connection_repo = UserConnectionRepository()

        # Process activities via callback URLs
        if "activities" in payload:
            for activity in payload["activities"]:
                try:
                    garmin_user_id = activity.get("userId")
                    callback_url = activity.get("callbackURL")

                    if not callback_url:
                        log_structured(
                            logger,
                            "warning",
                            "No callback URL in activity notification",
                            provider="garmin",
                            trace_id=request_trace_id,
                            garmin_user_id=garmin_user_id,
                        )
                        continue

                    # Find internal user_id based on garmin_user_id
                    connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)

                    if not connection:
                        log_structured(
                            logger,
                            "warning",
                            "No connection found for Garmin user",
                            provider="garmin",
                            trace_id=request_trace_id,
                            garmin_user_id=garmin_user_id,
                        )
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    internal_user_id = connection.user_id
                    # Use backfill trace_id if active, otherwise request-level
                    trace_id = get_trace_id(internal_user_id) or request_trace_id

                    log_structured(
                        logger,
                        "info",
                        "Activity callback URL received",
                        provider="garmin",
                        trace_id=trace_id,
                        garmin_user_id=garmin_user_id,
                        internal_user_id=str(internal_user_id),
                    )

                    # Fetch activity data from callback URL
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

                        processed_count += 1
                        processed_activities.append(
                            {
                                "garmin_user_id": garmin_user_id,
                                "internal_user_id": str(internal_user_id),
                                "activities_count": len(activities_data) if isinstance(activities_data, list) else 1,
                                "status": "fetched",
                            },
                        )

                    except httpx.HTTPError as e:
                        log_structured(
                            logger,
                            "error",
                            "Failed to fetch activity data from callback URL",
                            provider="garmin",
                            trace_id=trace_id,
                            error=str(e),
                        )
                        errors.append(f"HTTP error: {str(e)}")

                except Exception as e:
                    log_structured(
                        logger,
                        "error",
                        "Error processing activity notification",
                        provider="garmin",
                        trace_id=request_trace_id,
                        error=str(e),
                    )
                    errors.append(str(e))

        # Process all wellness data types via callback URLs
        # Full list of Garmin wellness summary types from backfill API
        wellness_types = [
            "dailies",
            "epochs",
            "sleeps",
            "bodyComps",
            "hrv",
            "stressDetails",
            "respiration",
            "pulseOx",
            "healthSnapshot",
            "skinTemp",
            "moveiq",
            "mct",
            "userMetrics",
            "bloodPressures",
            "activityDetails",
        ]

        wellness_results: dict[str, Any] = {}

        # Get Garmin 247 data service for processing wellness data
        factory = ProviderFactory()
        garmin_strategy = factory.get_provider("garmin")
        garmin_247 = cast(Garmin247Data, garmin_strategy.data_247)

        for summary_type in wellness_types:
            if summary_type in payload and payload[summary_type]:
                log_structured(
                    logger,
                    "info",
                    "Processing wellness notifications",
                    provider="garmin",
                    trace_id=request_trace_id,
                    summary_type=summary_type,
                    count=len(payload[summary_type]),
                )
                wellness_results[summary_type] = _process_wellness_notification(
                    db, summary_type, payload[summary_type], garmin_247, request_trace_id
                )

        # Commit all batch-inserted wellness data (bulk_create defers commit to caller)
        db.commit()

        # Extract user IDs from wellness results and update last_synced_at
        for result in wellness_results.values():
            if isinstance(result, dict):
                for item in result.get("items", []):
                    if item.get("saved", 0) > 0:
                        synced_user_ids.add(UUID(item["internal_user_id"]))
        if synced_user_ids:
            for uid in synced_user_ids:
                connection = user_connection_repo.get_active_connection(db, uid, "garmin")
                if connection:
                    user_connection_repo.update_last_synced_at(db, connection)

        # Collect user IDs with new success transitions from wellness results
        users_with_new_success: set[str] = set()
        for result in wellness_results.values():
            if isinstance(result, dict):
                users_with_new_success.update(result.get("new_success_users", []))

        # Also mark activities from PING callbacks
        for act in processed_activities:
            uid_str = act.get("internal_user_id")
            if uid_str and act.get("status") == "fetched" and mark_type_success(uid_str, "activities"):
                users_with_new_success.add(uid_str)

        # Chain next backfill type for users with new success transitions
        backfill_triggered = []
        for user_id_str in users_with_new_success:
            backfill_status = get_backfill_status(user_id_str)
            if backfill_status["overall_status"] == "in_progress":
                trigger_next_pending_type.delay(user_id_str)
                backfill_triggered.append(user_id_str)

        response: dict[str, Any] = {
            "processed": processed_count,
            "errors": errors,
            "activities": processed_activities,
            "wellness": wellness_results,
            "backfill_chained": backfill_triggered,
        }

        if "userPermissionsChange" in payload:
            try:
                response["userPermissionsChange"] = _process_user_permissions(
                    db, payload["userPermissionsChange"], request_trace_id
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
                response["deregistrations"] = _process_deregistrations(db, payload["deregistrations"], request_trace_id)
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

        return response
    except Exception as e:
        db.rollback()
        log_structured(
            logger,
            "error",
            "Error processing Garmin PING task",
            provider="garmin",
            trace_id=request_trace_id,
            error=str(e),
            retries=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task(
    bind=True,
    queue=GARMIN_SYNC_QUEUE,
    max_retries=2,
    default_retry_delay=60,  # retry after 1 minute if it fails
    acks_late=True,  # only acknowledge the task after it completes successfully
    reject_on_worker_lost=True,  # re-queue the task if the worker processing it dies
)
def process_push(self: Task, payload: dict[str, Any], request_trace_id: str) -> dict[str, Any]:
    """Process a Garmin PUSH webhook payload asynchronously as a Celery task.

    Args:
        payload: The JSON payload from the Garmin PUSH webhook.
        request_trace_id: Trace ID from the incoming webhook request for logging correlation.
    """
    db = SessionLocal()
    try:
        processed_count = 0
        saved_count = 0
        errors: list[str] = []
        processed_activities: list[dict] = []
        synced_user_ids: set[UUID] = set()

        # Get Garmin workouts service via factory
        factory = ProviderFactory()
        garmin_strategy = factory.get_provider("garmin")

        if not isinstance(garmin_strategy.workouts, GarminWorkouts):
            log_structured(
                logger,
                "error",
                "Garmin workouts service not available",
                provider="garmin",
                trace_id=request_trace_id,
            )
            return {"error": "Garmin workouts service not available"}

        garmin_workouts: GarminWorkouts = garmin_strategy.workouts
        garmin_247 = cast(Garmin247Data, garmin_strategy.data_247)
        user_connection_repo = UserConnectionRepository()

        # Process activities
        if "activities" in payload:
            for activity_notification in payload["activities"]:
                garmin_user_id = activity_notification.get("userId")
                activity_id = activity_notification.get("activityId")
                activity_name = activity_notification.get("activityName")
                activity_type = activity_notification.get("activityType")

                try:
                    # Map garmin_user_id to internal user_id
                    connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    if not connection:
                        log_structured(
                            logger,
                            "warning",
                            "No connection found for Garmin user",
                            provider="garmin",
                            trace_id=request_trace_id,
                            garmin_user_id=garmin_user_id,
                        )
                        errors.append(f"User {garmin_user_id} not connected")
                        processed_activities.append(
                            {
                                "activity_id": activity_id,
                                "name": activity_name,
                                "type": activity_type,
                                "garmin_user_id": garmin_user_id,
                                "status": "user_not_found",
                            },
                        )
                        continue

                    internal_user_id = connection.user_id
                    # Use backfill trace_id if active, otherwise request-level
                    trace_id = get_trace_id(internal_user_id) or request_trace_id

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

                    # Parse activity data using schema
                    try:
                        activity = GarminActivityJSON(**activity_notification)
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
                        errors.append(f"Invalid activity data for {activity_id}: {str(e)}")
                        processed_activities.append(
                            {
                                "activity_id": activity_id,
                                "name": activity_name,
                                "type": activity_type,
                                "garmin_user_id": garmin_user_id,
                                "status": "validation_error",
                            },
                        )
                        continue

                    # Save to database
                    created_ids = garmin_workouts.process_push_activities(
                        db=db,
                        activities=[activity],
                        user_id=internal_user_id,
                    )

                    saved_count += len(created_ids)
                    processed_activities.append(
                        {
                            "activity_id": activity_id,
                            "name": activity_name,
                            "type": activity_type,
                            "garmin_user_id": garmin_user_id,
                            "internal_user_id": str(internal_user_id),
                            "record_ids": [str(rid) for rid in created_ids],
                            "status": "saved",
                        },
                    )
                    processed_count += 1
                    if created_ids:
                        synced_user_ids.add(internal_user_id)
                    log_structured(
                        logger,
                        "info",
                        "Saved activity",
                        provider="garmin",
                        trace_id=trace_id,
                        activity_id=activity_id,
                        record_ids=[str(rid) for rid in created_ids],
                    )
                    # Activities backfill tracking is handled in the
                    # backfill chaining section below (with dedup protection)

                except IntegrityError:
                    # Duplicate activity - already exists in database
                    db.rollback()
                    log_structured(
                        logger,
                        "info",
                        "Activity already exists, skipping",
                        provider="garmin",
                        trace_id=request_trace_id,
                        activity_id=activity_id,
                    )
                    processed_activities.append(
                        {
                            "activity_id": activity_id,
                            "name": activity_name,
                            "type": activity_type,
                            "garmin_user_id": garmin_user_id,
                            "status": "duplicate",
                        },
                    )
                    processed_count += 1

                except Exception as e:
                    log_structured(
                        logger,
                        "error",
                        "Error processing activity notification",
                        provider="garmin",
                        trace_id=request_trace_id,
                        activity_id=activity_id,
                        error=str(e),
                    )
                    errors.append(f"Error processing activity {activity_id}: {str(e)}")

        # Process all wellness data types (batch processing)
        wellness_results: dict[str, Any] = {}
        users_with_new_success: set[str] = set()  # Track first-time successes only

        # All wellness data types to process
        wellness_types = [
            "sleeps",
            "dailies",
            "epochs",
            "bodyComps",
            "hrv",
            "stressDetails",
            "respiration",
            "pulseOx",
            "bloodPressures",
            "userMetrics",
            "skinTemp",
            "healthSnapshot",
            "moveiq",
            "mct",
            "activityDetails",
        ]

        for data_type in wellness_types:
            if data_type not in payload:
                continue

            # Group items by user for batch processing
            user_items: dict[UUID, list[dict[str, Any]]] = {}
            for item_data in payload[data_type]:
                try:
                    garmin_user_id = item_data.get("userId")
                    connection = user_connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    if not connection:
                        log_structured(
                            logger,
                            "warning",
                            "No connection for Garmin user",
                            provider="garmin",
                            trace_id=request_trace_id,
                            garmin_user_id=garmin_user_id,
                            data_type=data_type,
                        )
                        continue
                    user_items.setdefault(connection.user_id, []).append(item_data)
                except Exception as e:
                    log_structured(
                        logger,
                        "error",
                        f"Error resolving user for {data_type}",
                        provider="garmin",
                        trace_id=request_trace_id,
                        error=str(e),
                    )
                    errors.append(f"{data_type} error: {str(e)}")

            type_count = 0
            type_users: set[str] = set()
            for uid, items in user_items.items():
                trace_id = get_trace_id(uid) or request_trace_id
                try:
                    count = garmin_247.process_items_batch(db, uid, data_type, items)
                    type_count += count
                    type_users.add(str(uid))
                    if count > 0:
                        synced_user_ids.add(uid)
                except Exception as e:
                    log_structured(
                        logger,
                        "error",
                        f"Error processing {data_type}",
                        provider="garmin",
                        trace_id=trace_id,
                        user_id=str(uid),
                        error=str(e),
                    )
                    errors.append(f"{data_type} error: {str(e)}")

            if type_count > 0:
                log_structured(
                    logger,
                    "info",
                    f"Saved {data_type} records",
                    provider="garmin",
                    trace_id=request_trace_id,
                    data_type=data_type,
                    count=type_count,
                    user_count=len(type_users),
                )
                for uid_str in type_users:
                    if mark_type_success(uid_str, data_type):
                        # First success for this type — schedule next backfill
                        users_with_new_success.add(uid_str)

            wellness_results[data_type] = {
                "processed": len(payload[data_type]),
                "saved": type_count,
            }

        # Commit all batch-inserted wellness data (bulk_create defers commit to caller)
        db.commit()

        # Update last_synced_at for all users that received data via push
        for uid in synced_user_ids:
            connection = user_connection_repo.get_active_connection(db, uid, "garmin")
            if connection:
                user_connection_repo.update_last_synced_at(db, connection)

        # Also add users from activity processing (only if newly succeeded)
        for act in processed_activities:
            uid_str = act.get("internal_user_id")
            if uid_str and act.get("status") == "saved" and mark_type_success(uid_str, "activities"):
                users_with_new_success.add(uid_str)

        # Chain next backfill request ONLY for users with a new type transition.
        # This prevents duplicate triggers when Garmin sends multiple webhooks
        # for the same data type (e.g. epochs split across many payloads).
        backfill_triggered = []
        for user_id_str in users_with_new_success:
            backfill_status = get_backfill_status(user_id_str)
            if backfill_status["overall_status"] == "in_progress":
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
                trigger_next_pending_type.delay(user_id_str)
                backfill_triggered.append(user_id_str)

        response: dict[str, Any] = {
            "processed": processed_count,
            "saved": saved_count,
            "errors": errors,
            "activities": processed_activities,
            "wellness": wellness_results,
            "backfill_chained": backfill_triggered,
        }

        if "userPermissionsChange" in payload:
            try:
                response["userPermissionsChange"] = _process_user_permissions(
                    db, payload["userPermissionsChange"], request_trace_id
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
                response["deregistrations"] = _process_deregistrations(db, payload["deregistrations"], request_trace_id)
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

        return response
    except Exception as e:
        db.rollback()
        log_structured(
            logger,
            "error",
            "Error processing Garmin PUSH task",
            provider="garmin",
            trace_id=request_trace_id,
            error=str(e),
            retries=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=e)
    finally:
        db.close()
