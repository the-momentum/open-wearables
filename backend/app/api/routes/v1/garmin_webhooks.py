"""Garmin webhook endpoints for receiving push/ping notifications."""

from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from app.database import DbSession
from app.services import garmin_import_service

router = APIRouter()
logger = getLogger(__name__)


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
        results = {
            "processed": 0,
            "errors": [],
        }

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
                    from app.repositories import UserConnectionRepository

                    repo = UserConnectionRepository()
                    connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)

                    if not connection:
                        logger.warning(f"No connection found for Garmin user {garmin_user_id}")
                        results["errors"].append(f"User {garmin_user_id} not connected")
                        continue

                    internal_user_id = connection.user_id
                    logger.info(f"Mapped Garmin user {garmin_user_id} to internal user {internal_user_id}")

                    # Extract parameters from callback URL (including pull token)
                    from urllib.parse import parse_qs, urlparse

                    parsed_url = urlparse(callback_url)
                    query_params = parse_qs(parsed_url.query)
                    pull_token = query_params.get("token", [None])[0]
                    upload_start = query_params.get("uploadStartTimeInSeconds", [None])[0]
                    upload_end = query_params.get("uploadEndTimeInSeconds", [None])[0]

                    if pull_token:
                        # Save pull token to Redis for later use
                        # Token is associated with user and time range
                        import redis

                        from app.config import settings

                        redis_client = redis.Redis(
                            host=settings.redis_host,
                            port=settings.redis_port,
                            db=settings.redis_db,
                            decode_responses=True,
                        )

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
                    import httpx

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

                        results["processed"] += 1
                        results["activities"].append(
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
                        results["errors"].append(f"HTTP error: {str(e)}")

                except Exception as e:
                    logger.error(f"Error processing activity notification: {str(e)}")
                    results["errors"].append(str(e))

            # temporary visual change
            try:
                garmin_import_service.load_data(db, payload["activities"], internal_user_id)
            except Exception as e:
                logger.error(f"Error loading data from Garmin: {str(e)}")
                results["errors"].append(f"Error loading data from Garmin: {str(e)}")

        # Process other summary types (activityDetails, dailies, etc.)
        for summary_type in ["activityDetails", "dailies", "epochs", "sleeps"]:
            if summary_type in payload:
                logger.info(f"Received {len(payload[summary_type])} {summary_type} notifications")
                # TODO: Process other summary types similarly

        return results

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

        results = {
            "processed": 0,
            "errors": [],
            "activities": [],
        }

        # Process activities
        if "activities" in payload:
            for activity_notification in payload["activities"]:
                try:
                    garmin_user_id = activity_notification.get("userId")
                    activity_id = activity_notification.get("activityId")
                    activity_name = activity_notification.get("activityName")
                    activity_type = activity_notification.get("activityType")

                    logger.info(
                        f"New Garmin activity: {activity_name} ({activity_type}) "
                        f"ID={activity_id} for user {garmin_user_id}",
                    )

                    # TODO: Map garmin_user_id to internal user_id
                    # from app.repositories import UserConnectionRepository
                    # repo = UserConnectionRepository()
                    # connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    # if not connection:
                    #     logger.warning(f"No connection found for Garmin user {garmin_user_id}")
                    #     continue
                    # internal_user_id = connection.user_id

                    # TODO: Fetch full activity details from Garmin API
                    # from app.services.garmin_service import garmin_service
                    # full_activity = garmin_service.get_activity_detail(
                    #     db=db,
                    #     user_id=internal_user_id,
                    #     activity_id=str(activity_id),
                    # )

                    # TODO: Save to database
                    # Parse and store activity data...

                    results["activities"].append(
                        {
                            "activity_id": activity_id,
                            "name": activity_name,
                            "type": activity_type,
                            "garmin_user_id": garmin_user_id,
                            "status": "received",
                        },
                    )
                    results["processed"] += 1

                except Exception as e:
                    logger.error(f"Error processing activity notification: {str(e)}")
                    results["errors"].append(str(e))

            # no internal user id, just temporary visual change
            try:
                garmin_import_service.load_data(db, payload["activities"], internal_user_id)
            except Exception as e:
                logger.error(f"Error loading data from Garmin: {str(e)}")
                results["errors"].append(f"Error loading data from Garmin: {str(e)}")

        return results

    except Exception as e:
        logger.error(f"Error processing Garmin push webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.get("/health")
async def garmin_webhook_health() -> dict:
    """Health check endpoint for Garmin webhook configuration."""
    return {"status": "ok", "service": "garmin-webhooks"}
