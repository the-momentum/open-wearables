"""Garmin webhook endpoints for receiving push/ping notifications."""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Annotated, Any, cast
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.integrations.celery.tasks.garmin_backfill_task import (
    get_backfill_status,
    trigger_next_backfill,
)
from app.integrations.redis_client import get_redis_client
from app.models import Developer
from app.repositories import UserConnectionRepository
from app.schemas import GarminActivityJSON
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.providers.garmin.workouts import GarminWorkouts
from app.utils.auth import get_current_developer

router = APIRouter()
logger = getLogger(__name__)


async def _process_wellness_notification(
    db: DbSession,
    summary_type: str,
    notifications: list[dict[str, Any]],
    garmin_247: Garmin247Data,
) -> dict[str, Any]:
    """Process wellness data notifications (dailies, epochs, sleeps).

    Args:
        db: Database session
        summary_type: Type of data ("dailies", "epochs", "sleeps")
        notifications: List of notification items from webhook payload
        garmin_247: Garmin 247 data service instance

    Returns:
        Dict with processing results
    """
    results: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "errors": [],
        "items": [],
    }

    repo = UserConnectionRepository()

    for notification in notifications:
        garmin_user_id = notification.get("userId")
        callback_url = notification.get("callbackURL")

        if not callback_url:
            logger.warning(f"No callback URL in {summary_type} notification for user {garmin_user_id}")
            continue

        # Find internal user
        if not garmin_user_id:
            logger.warning(f"No user ID in {summary_type} notification")
            continue
        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            logger.warning(f"No connection found for Garmin user {garmin_user_id}")
            results["errors"].append(f"User {garmin_user_id} not connected")
            continue

        user_id: UUID = connection.user_id
        logger.info(f"Processing {summary_type} for user {user_id} (Garmin: {garmin_user_id})")

        try:
            # Fetch data from callback URL
            async with httpx.AsyncClient() as client:
                response = await client.get(callback_url, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, list):
                data = [data]

            logger.info(f"Fetched {len(data)} {summary_type} items for user {user_id}")

            # Process based on type
            count = 0
            for item in data:
                try:
                    if summary_type == "sleeps":
                        normalized = garmin_247.normalize_sleep(item, user_id)
                        garmin_247.save_sleep_data(db, user_id, normalized)
                        count += 1
                    elif summary_type == "dailies":
                        normalized = garmin_247.normalize_dailies(item, user_id)
                        count += garmin_247.save_dailies_data(db, user_id, normalized)
                    elif summary_type == "epochs":
                        # Normalize and save single epoch
                        normalized = garmin_247.normalize_epochs([item], user_id)
                        count += garmin_247.save_epochs_data(db, user_id, normalized)
                    elif summary_type == "bodyComps":
                        # Body composition data
                        count += garmin_247.save_body_composition(db, user_id, item)
                    else:
                        # Log unsupported types for future implementation
                        logger.info(
                            f"Received {summary_type} data for user {user_id} "
                            f"(type not yet fully implemented, logging only)"
                        )
                        count += 1  # Count as processed even if not saved
                except Exception as e:
                    logger.warning(f"Error processing {summary_type} item: {e}")
                    results["errors"].append(f"Error processing item: {str(e)}")

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

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {summary_type}: {str(e)}")
            results["errors"].append(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing {summary_type} notification: {str(e)}")
            results["errors"].append(f"Error: {str(e)}")

    return results


@router.post("/ping")
async def garmin_ping_notification(
    request: Request,
    db: DbSession,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PING notifications.

    Garmin sends ping notifications when new data is available.
    The notification contains a callbackURL with a temporary pull token
    that can be used to fetch the actual data.

    Expected format:
    {
        "activities": [{
            "userId": "garmin_user_id",
            "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?...&token=XXXXX"
        }],
        "activityDetails": [...],
        "dailies": [...],
        ...
    }
    """
    # Verify request is from Garmin
    if not garmin_client_id:
        logger.warning("Received webhook without garmin-client-id header")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    # TODO: Verify garmin_client_id matches your application's client ID
    # from app.config import settings
    # if garmin_client_id != settings.garmin_client_id:
    #     raise HTTPException(status_code=401, detail="Invalid client ID")

    try:
        payload = await request.json()
        logger.info(f"Received Garmin ping notification: {payload}")

        # Process different summary types
        processed_count = 0
        errors: list[str] = []
        processed_activities: list[dict] = []

        # Process activities
        if "activities" in payload:
            for activity in payload["activities"]:
                try:
                    garmin_user_id = activity.get("userId")
                    callback_url = activity.get("callbackURL")

                    if not callback_url:
                        logger.warning(f"No callback URL in activity notification for user {garmin_user_id}")
                        continue

                    logger.info(f"Activity callback URL for user {garmin_user_id}: {callback_url}")

                    # Find internal user_id based on garmin_user_id
                    repo = UserConnectionRepository()
                    connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)

                    if not connection:
                        logger.warning(f"No connection found for Garmin user {garmin_user_id}")
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    internal_user_id = connection.user_id
                    logger.info(f"Mapped Garmin user {garmin_user_id} to internal user {internal_user_id}")

                    # Extract parameters from callback URL (including pull token)
                    parsed_url = urlparse(callback_url)
                    query_params = parse_qs(parsed_url.query)
                    pull_token = query_params.get("token", [None])[0]
                    upload_start = query_params.get("uploadStartTimeInSeconds", [None])[0]
                    upload_end = query_params.get("uploadEndTimeInSeconds", [None])[0]

                    if pull_token:
                        # Save pull token to Redis for later use
                        # Token is associated with user and time range
                        redis_client = get_redis_client()

                        # Create key: garmin_token:{user_id}:{timestamp_range}
                        token_key = f"garmin_pull_token:{internal_user_id}:{upload_start}_{upload_end}"
                        redis_client.setex(
                            token_key,
                            3600,  # Token valid for 1 hour (adjust based on Garmin's actual expiry)
                            pull_token,
                        )

                        logger.info(
                            f"Saved pull token for user {internal_user_id} (time range: {upload_start}-{upload_end})",
                        )

                        # Also save the full callback URL for convenience
                        url_key = f"garmin_callback_url:{internal_user_id}:latest"
                        redis_client.setex(url_key, 3600, callback_url)

                    # Optionally: Fetch and cache activity data immediately
                    # This is recommended so data is available even if token expires
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(callback_url, timeout=30.0)
                            response.raise_for_status()
                            activities_data = response.json()

                        logger.info(
                            f"Fetched {len(activities_data) if isinstance(activities_data, list) else 1} "
                            f"activities for user {internal_user_id}",
                        )

                        # TODO: Parse and save to database
                        # For now, just log the data structure
                        logger.debug(f"Activity data: {activities_data}")

                        processed_count += 1
                        processed_activities.append(
                            {
                                "garmin_user_id": garmin_user_id,
                                "internal_user_id": str(internal_user_id),
                                "activities_count": len(activities_data) if isinstance(activities_data, list) else 1,
                                "status": "fetched",
                                "pull_token_saved": True,
                            },
                        )

                    except httpx.HTTPError as e:
                        logger.error(f"Failed to fetch activity data from callback URL: {str(e)}")
                        errors.append(f"HTTP error: {str(e)}")

                except Exception as e:
                    logger.error(f"Error processing activity notification: {str(e)}")
                    errors.append(str(e))

        # Process wellness data types
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
        ]

        wellness_results: dict[str, Any] = {}

        # Get Garmin 247 data service for processing wellness data
        factory = ProviderFactory()
        garmin_strategy = factory.get_provider("garmin")

        if hasattr(garmin_strategy, "data_247") and garmin_strategy.data_247:
            garmin_247 = cast(Garmin247Data, garmin_strategy.data_247)

            for summary_type in wellness_types:
                if summary_type in payload and payload[summary_type]:
                    logger.info(f"Processing {len(payload[summary_type])} {summary_type} notifications")
                    wellness_results[summary_type] = await _process_wellness_notification(
                        db, summary_type, payload[summary_type], garmin_247
                    )
        else:
            # Log but don't fail if data_247 is not available
            for summary_type in wellness_types:
                if summary_type in payload:
                    logger.warning(
                        f"Received {len(payload[summary_type])} {summary_type} notifications "
                        f"but Garmin 247 data service is not available"
                    )

        # Also log activity details (not yet implemented)
        if "activityDetails" in payload:
            logger.info(f"Received {len(payload['activityDetails'])} activityDetails notifications (not processed)")

        return {
            "processed": processed_count,
            "errors": errors,
            "activities": processed_activities,
            "wellness": wellness_results,
        }

    except Exception as e:
        logger.error(f"Error processing Garmin webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/push")
async def garmin_push_notification(
    request: Request,
    db: DbSession,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PUSH notifications.

    Push notifications contain basic activity metadata.
    Use the activityId to fetch full activity details from Garmin API.

    Expected format:
    {
        "activities": [{
            "userId": "garmin_user_id",
            "summaryId": "21047282990",
            "activityId": 21047282990,
            "activityName": "Morning Run",
            "startTimeInSeconds": 1763597760,
            "startTimeOffsetInSeconds": 3600,
            "activityType": "RUNNING",
            "deviceName": "Forerunner 965",
            "manual": false,
            "isWebUpload": false
        }]
    }
    """
    # Verify request is from Garmin
    if not garmin_client_id:
        logger.warning("Received webhook without garmin-client-id header")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        payload = await request.json()
        logger.info(f"Received Garmin push notification: {payload}")

        processed_count = 0
        saved_count = 0
        errors: list[str] = []
        processed_activities: list[dict] = []

        # Get Garmin workouts service via factory
        factory = ProviderFactory()
        garmin_strategy = factory.get_provider("garmin")
        if not isinstance(garmin_strategy.workouts, GarminWorkouts):
            raise HTTPException(status_code=500, detail="Garmin workouts service not available")
        garmin_workouts: GarminWorkouts = garmin_strategy.workouts

        # Process activities
        if "activities" in payload:
            for activity_notification in payload["activities"]:
                garmin_user_id = activity_notification.get("userId")
                activity_id = activity_notification.get("activityId")
                activity_name = activity_notification.get("activityName")
                activity_type = activity_notification.get("activityType")

                try:
                    logger.info(
                        f"New Garmin activity: {activity_name} ({activity_type}) "
                        f"ID={activity_id} for user {garmin_user_id}",
                    )

                    # Map garmin_user_id to internal user_id
                    repo = UserConnectionRepository()
                    connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    if not connection:
                        logger.warning(f"No connection found for Garmin user {garmin_user_id}")
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
                    logger.info(f"Mapped Garmin user {garmin_user_id} to internal user {internal_user_id}")

                    # Parse activity data using schema
                    try:
                        activity = GarminActivityJSON(**activity_notification)
                    except ValidationError as e:
                        logger.error(f"Failed to parse activity data: {e}")
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
                    logger.info(f"Saved activity {activity_id} with record IDs: {created_ids}")

                except IntegrityError:
                    # Duplicate activity - already exists in database
                    db.rollback()
                    logger.info(f"Activity {activity_id} already exists, skipping")
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
                    logger.error(f"Error processing activity notification: {str(e)}")
                    errors.append(f"Error processing activity {activity_id}: {str(e)}")

        # Process wellness data types (sleeps, dailies, epochs, bodyComps)
        wellness_results: dict[str, Any] = {}

        if hasattr(garmin_strategy, "data_247") and garmin_strategy.data_247:
            garmin_247 = cast(Garmin247Data, garmin_strategy.data_247)
            repo = UserConnectionRepository()

            # Handle sleeps (batch processing - log once at end)
            if "sleeps" in payload:
                sleep_count = 0
                sleeps_users: set[str] = set()
                for sleep_data in payload["sleeps"]:
                    try:
                        garmin_user_id = sleep_data.get("userId")
                        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                        if connection:
                            normalized = garmin_247.normalize_sleep(sleep_data, connection.user_id)
                            garmin_247.save_sleep_data(db, connection.user_id, normalized)
                            sleep_count += 1
                            sleeps_users.add(str(connection.user_id))
                        else:
                            logger.warning(f"No connection for Garmin user {garmin_user_id} (sleeps)")
                    except Exception as e:
                        logger.error(f"Error processing sleep: {e}")
                        errors.append(f"Sleep error: {str(e)}")
                if sleep_count > 0:
                    logger.info(f"Saved {sleep_count} sleep records for {len(sleeps_users)} user(s)")
                wellness_results["sleeps"] = {"processed": len(payload["sleeps"]), "saved": sleep_count}

            # Handle dailies (batch processing - log once at end)
            if "dailies" in payload:
                dailies_count = 0
                dailies_users: set[str] = set()
                for daily_data in payload["dailies"]:
                    try:
                        garmin_user_id = daily_data.get("userId")
                        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                        if connection:
                            normalized = garmin_247.normalize_dailies(daily_data, connection.user_id)
                            dailies_count += garmin_247.save_dailies_data(db, connection.user_id, normalized)
                            dailies_users.add(str(connection.user_id))
                        else:
                            logger.warning(f"No connection for Garmin user {garmin_user_id} (dailies)")
                    except Exception as e:
                        logger.error(f"Error processing dailies: {e}")
                        errors.append(f"Dailies error: {str(e)}")
                if dailies_count > 0:
                    logger.info(f"Saved {dailies_count} dailies records for {len(dailies_users)} user(s)")
                wellness_results["dailies"] = {"processed": len(payload["dailies"]), "saved": dailies_count}

            # Handle epochs (batch processing - log once at end)
            if "epochs" in payload:
                epochs_count = 0
                epochs_processed = 0
                epochs_users: set[str] = set()
                for epoch_data in payload["epochs"]:
                    try:
                        garmin_user_id = epoch_data.get("userId")
                        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                        if connection:
                            normalized = garmin_247.normalize_epochs([epoch_data], connection.user_id)
                            epochs_count += garmin_247.save_epochs_data(db, connection.user_id, normalized)
                            epochs_users.add(str(connection.user_id))
                        else:
                            logger.warning(f"No connection for Garmin user {garmin_user_id} (epochs)")
                        epochs_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing epochs: {e}")
                        errors.append(f"Epochs error: {str(e)}")
                # Log once per batch instead of per epoch
                if epochs_count > 0:
                    logger.info(
                        f"Saved {epochs_count} epochs records for {len(epochs_users)} user(s) "
                        f"(processed {epochs_processed}/{len(payload['epochs'])} items)"
                    )
                wellness_results["epochs"] = {"processed": len(payload["epochs"]), "saved": epochs_count}

            # Handle bodyComps (batch processing - log once at end)
            if "bodyComps" in payload:
                body_count = 0
                bodycomps_users: set[str] = set()
                for body_data in payload["bodyComps"]:
                    try:
                        garmin_user_id = body_data.get("userId")
                        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                        if connection:
                            body_count += garmin_247.save_body_composition(db, connection.user_id, body_data)
                            bodycomps_users.add(str(connection.user_id))
                        else:
                            logger.warning(f"No connection for Garmin user {garmin_user_id} (bodyComps)")
                    except Exception as e:
                        logger.error(f"Error processing bodyComps: {e}")
                        errors.append(f"BodyComps error: {str(e)}")
                if body_count > 0:
                    logger.info(f"Saved {body_count} body composition records for {len(bodycomps_users)} user(s)")
                wellness_results["bodyComps"] = {"processed": len(payload["bodyComps"]), "saved": body_count}

            # Handle HRV (Heart Rate Variability) - batch processing
            if "hrv" in payload:
                hrv_count = 0
                hrv_users: set[str] = set()
                for hrv_data in payload["hrv"]:
                    try:
                        garmin_user_id = hrv_data.get("userId")
                        connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                        if connection:
                            hrv_count += garmin_247.save_hrv_data(db, connection.user_id, hrv_data)
                            hrv_users.add(str(connection.user_id))
                        else:
                            logger.warning(f"No connection for Garmin user {garmin_user_id} (hrv)")
                    except Exception as e:
                        logger.error(f"Error processing HRV: {e}")
                        errors.append(f"HRV error: {str(e)}")
                if hrv_count > 0:
                    logger.info(f"Saved {hrv_count} HRV records for {len(hrv_users)} user(s)")
                wellness_results["hrv"] = {"processed": len(payload["hrv"]), "saved": hrv_count}

        # Collect all user IDs that were processed for wellness data
        all_users: set[str] = set()
        if "sleeps_users" in dir():
            all_users.update(sleeps_users)
        if "dailies_users" in dir():
            all_users.update(dailies_users)
        if "epochs_users" in dir():
            all_users.update(epochs_users)
        if "bodycomps_users" in dir():
            all_users.update(bodycomps_users)
        if "hrv_users" in dir():
            all_users.update(hrv_users)

        # Chain next backfill request for users with active backfill
        # Sequential flow: each webhook triggers the NEXT data type
        # sleeps → webhook → dailies → webhook → epochs → ... → next day
        backfill_triggered = []
        for user_id_str in all_users:
            status = get_backfill_status(user_id_str)
            if status["in_progress"]:
                logger.info(
                    f"Triggering next backfill for user {user_id_str} "
                    f"(day {status['days_completed'] + 1}/{status['target_days']}, "
                    f"next type: {status['current_data_type']})"
                )
                trigger_next_backfill.delay(user_id_str)
                backfill_triggered.append(user_id_str)

        return {
            "processed": processed_count,
            "saved": saved_count,
            "errors": errors,
            "activities": processed_activities,
            "wellness": wellness_results,
            "backfill_chained": backfill_triggered,
        }

    except Exception as e:
        logger.error(f"Error processing Garmin push webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.get("/health")
async def garmin_webhook_health() -> dict:
    """Health check endpoint for Garmin webhook configuration."""
    return {"status": "ok", "service": "garmin-webhooks"}


@router.get("/verify-pull-token")
async def verify_pull_token(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
    token: Annotated[str, Query(description="Manual pull token from Garmin Dashboard")],
    data_type: Annotated[
        str,
        Query(description="Data type: sleeps, dailies, epochs, bodyComps, hrv, stressDetails, respiration, pulseOx"),
    ] = "sleeps",
    start_days_ago: Annotated[int, Query(description="Start date (days ago from now)")] = 7,
    end_days_ago: Annotated[int, Query(description="End date (days ago from now)")] = 0,
) -> dict:
    """
    Verify endpoint to fetch Garmin data using a manually generated pull token.

    This endpoint is for testing purposes only. It allows you to verify that:
    1. The pull token format is correct
    2. OAuth credentials work with pull tokens
    3. The data format matches expected schemas

    Usage:
    1. Go to Garmin Developer Dashboard → API Pull Token tool
    2. Generate a token for your test user
    3. Call this endpoint with the token

    Example:
    GET /api/v1/garmin/webhooks/verify-pull-token?token=<token>&data_type=sleeps
    """
    # Validate data type
    valid_data_types = [
        "sleeps",
        "dailies",
        "epochs",
        "bodyComps",
        "hrv",
        "stressDetails",
        "respiration",
        "pulseOx",
        "activities",
        "userMetrics",
    ]

    if data_type not in valid_data_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type. Must be one of: {', '.join(valid_data_types)}",
        )

    # Calculate time range
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=start_days_ago)
    end_time = now - timedelta(days=end_days_ago)

    # Build endpoint
    endpoint = f"/wellness-api/rest/{data_type}"

    params = {
        "uploadStartTimeInSeconds": int(start_time.timestamp()),
        "uploadEndTimeInSeconds": int(end_time.timestamp()),
        "token": token,
    }

    logger.info(
        f"Testing pull token for user {current_developer.id}: "
        f"data_type={data_type}, range={start_time.isoformat()} to {end_time.isoformat()}"
    )

    try:
        # Get Garmin provider for OAuth
        factory = ProviderFactory()
        garmin_strategy = factory.get_provider("garmin")

        if not garmin_strategy.oauth:
            raise HTTPException(status_code=500, detail="Garmin OAuth not configured")

        # Make authenticated request with pull token
        response = make_authenticated_request(
            db=db,
            user_id=current_developer.id,
            connection_repo=UserConnectionRepository(),
            oauth=garmin_strategy.oauth,
            api_base_url="https://apis.garmin.com",
            provider_name="garmin",
            endpoint=endpoint,
            method="GET",
            params=params,
            expect_json=True,
        )

        # Calculate record count
        record_count = len(response) if isinstance(response, list) else 1

        logger.info(f"Successfully fetched {record_count} {data_type} records for user {current_developer.id}")

        return {
            "success": True,
            "data_type": data_type,
            "record_count": record_count,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "data": response,
        }

    except HTTPException as e:
        logger.error(f"Pull token test failed: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Pull token test failed with unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch data: {str(e)}",
        )
