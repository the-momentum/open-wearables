from logging import getLogger
from typing import Annotated
from fastapi import Request, Query, HTTPException

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.services.providers.factory import ProviderFactory
from app.services.providers.strava.workouts import StravaWorkouts
from app.schemas import StravaActivityJSON
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from uuid import UUID


logger = getLogger(__name__)


async def handle_webhook_verification(hub_mode: Annotated[str, Query(alias="hub.mode")] = "",
    hub_challenge: Annotated[str, Query(alias="hub.challenge")] = "",
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")] = "",) -> dict:
    """Handle Strava webhook subscription verification."""
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    if hub_verify_token != settings.strava_webhook_verify_token:
        logger.warning(f"Invalid verify token received: {hub_verify_token}")
        raise HTTPException(status_code=403, detail="Invalid verify token")

    logger.info("Strava webhook subscription verified successfully")
    return {"hub.challenge": hub_challenge}


async def handle_webhook_event(request: Request, db: DbSession) -> dict:
    """Handle Strava webhook event."""
    try:
        payload = await request.json()
        logger.info(f"Received Strava webhook event: {payload}")

        object_type = payload.get("object_type")
        object_id = payload.get("object_id")
        aspect_type = payload.get("aspect_type")
        owner_id = payload.get("owner_id")  # Strava athlete ID

        # Only process activity events
        if object_type != "activity":
            logger.info(f"Ignoring non-activity event: {object_type}")
            return {"status": "ok", "message": f"Ignoring {object_type} event"}

        # Only process create and update events
        if aspect_type not in ("create", "update"):
            logger.info(f"Ignoring {aspect_type} event for activity {object_id}")
            return {"status": "ok", "message": f"Ignoring {aspect_type} event"}

        if not owner_id or not object_id:
            logger.warning("Missing owner_id or object_id in webhook payload")
            return {"status": "ok", "message": "Missing required fields"}

        # Map Strava athlete ID to internal user
        repo = UserConnectionRepository()
        connection = repo.get_by_provider_user_id(db, "strava", str(owner_id))

        if not connection:
            logger.warning(f"No connection found for Strava athlete {owner_id}")
            return {"status": "ok", "message": "User not connected"}

        internal_user_id: UUID = connection.user_id
        logger.info(f"Mapped Strava athlete {owner_id} to internal user {internal_user_id}")

        # Get Strava workouts service via factory
        factory = ProviderFactory()
        strava_strategy = factory.get_provider("strava")
        if not isinstance(strava_strategy.workouts, StravaWorkouts):
            logger.error("Strava workouts service not available")
            return {"status": "ok", "message": "Service unavailable"}

        strava_workouts: StravaWorkouts = strava_strategy.workouts

        try:
            # Fetch full activity detail from Strava API
            activity_data = strava_workouts.get_workout_detail_from_api(
                db, internal_user_id, str(object_id)
            )

            if not activity_data:
                logger.warning(f"No data returned for Strava activity {object_id}")
                return {"status": "ok", "message": "No activity data"}

            # Parse activity
            activity = StravaActivityJSON(**activity_data)

            # Save to database
            created_ids = strava_workouts.process_push_activity(
                db=db,
                activity=activity,
                user_id=internal_user_id,
            )

            logger.info(f"Saved Strava activity {object_id} with record IDs: {created_ids}")
            return {
                "status": "ok",
                "activity_id": object_id,
                "record_ids": [str(rid) for rid in created_ids],
            }

        except IntegrityError:
            db.rollback()
            logger.info(f"Strava activity {object_id} already exists, skipping")
            return {"status": "ok", "message": "Duplicate activity"}

        except ValidationError as e:
            logger.error(f"Failed to parse Strava activity {object_id}: {e}")
            return {"status": "ok", "message": "Validation error"}

        except Exception as e:
            logger.error(f"Error processing Strava activity {object_id}: {e}")
            return {"status": "ok", "message": "Processing error"}

    except Exception as e:
        logger.error(f"Error processing Strava webhook: {e}")
        # Always return 200 to prevent Strava retries
        return {"status": "ok", "message": "Error processing event"}