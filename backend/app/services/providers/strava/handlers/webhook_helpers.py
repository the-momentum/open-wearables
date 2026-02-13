from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas import StravaActivityJSON
from app.services.providers.strava.workouts import StravaWorkouts
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


async def handle_webhook_verification(
    hub_mode: Annotated[str, Query(alias="hub.mode")] = "",
    hub_challenge: Annotated[str, Query(alias="hub.challenge")] = "",
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")] = "",
) -> dict:
    """Handle Strava webhook subscription verification."""
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    if hub_verify_token != settings.strava_webhook_verify_token:
        log_structured(
            logger,
            "warn",
            "Invalid verify token received",
            provider="strava",
            action="webhook_verification_failed",
            verify_token=hub_verify_token,
        )
        raise HTTPException(status_code=403, detail="Invalid verify token")

    log_structured(
        logger,
        "info",
        "Strava webhook subscription verified successfully",
        provider="strava",
        action="webhook_verified",
    )
    return {"hub.challenge": hub_challenge}


async def handle_webhook_event(request: Request, db: DbSession) -> dict:
    """Handle Strava webhook event."""
    try:
        payload = await request.json()
        log_structured(
            logger,
            "info",
            "Received Strava webhook event",
            provider="strava",
            action="webhook_received",
            payload=payload,
        )

        object_type = payload.get("object_type")
        object_id = payload.get("object_id")
        aspect_type = payload.get("aspect_type")
        owner_id = payload.get("owner_id")  # Strava athlete ID

        # Only process activity events
        if object_type != "activity":
            log_structured(
                logger,
                "info",
                "Ignoring non-activity event",
                provider="strava",
                action="webhook_ignored",
                object_type=object_type,
            )
            return {"status": "ok", "message": f"Ignoring {object_type} event"}

        # Only process create and update events
        if aspect_type not in ("create", "update"):
            log_structured(
                logger,
                "info",
                "Ignoring aspect type event for activity",
                provider="strava",
                action="webhook_ignored",
                aspect_type=aspect_type,
                object_id=object_id,
            )
            return {"status": "ok", "message": f"Ignoring {aspect_type} event"}

        if not owner_id or not object_id:
            log_structured(
                logger,
                "warn",
                "Missing owner_id or object_id in webhook payload",
                provider="strava",
                action="webhook_invalid",
                owner_id=owner_id,
                object_id=object_id,
            )
            return {"status": "error", "message": "Missing required fields"}

        # Map Strava athlete ID to internal user
        user_repo = UserConnectionRepository()
        connection = user_repo.get_by_provider_user_id(db, "strava", str(owner_id))

        if not connection:
            log_structured(
                logger,
                "warn",
                "No connection found for Strava athlete",
                provider="strava",
                action="webhook_no_connection",
                strava_athlete_id=owner_id,
            )
            return {"status": "error", "message": "User not connected"}

        internal_user_id: UUID = connection.user_id
        log_structured(
            logger,
            "info",
            "Mapped Strava athlete to internal user",
            provider="strava",
            action="webhook_user_mapped",
            strava_athlete_id=owner_id,
            user_id=str(internal_user_id),
        )

        # Get Strava workouts service via factory (deferred import to avoid circular dependency)
        from app.services.providers.factory import ProviderFactory

        factory = ProviderFactory()
        strava_strategy = factory.get_provider("strava")
        if not isinstance(strava_strategy.workouts, StravaWorkouts):
            log_structured(
                logger,
                "error",
                "Strava workouts service not available",
                provider="strava",
                action="webhook_service_unavailable",
            )
            return {"status": "error", "message": "Service unavailable"}

        strava_workouts: StravaWorkouts = strava_strategy.workouts

        try:
            # Fetch full activity detail from Strava API
            activity_data = strava_workouts.get_workout_detail_from_api(db, internal_user_id, str(object_id))

            if not activity_data:
                log_structured(
                    logger,
                    "warn",
                    "No data returned for Strava activity",
                    provider="strava",
                    action="webhook_no_activity_data",
                    activity_id=object_id,
                    user_id=str(internal_user_id),
                )
                return {"status": "warning", "message": "No activity data"}

            # Parse activity
            activity = StravaActivityJSON(**activity_data)

            # Save to database
            created_ids = strava_workouts.process_push_activity(
                db=db,
                activity=activity,
                user_id=internal_user_id,
            )

            log_structured(
                logger,
                "info",
                "Saved Strava activity with record IDs",
                provider="strava",
                action="webhook_activity_saved",
                activity_id=object_id,
                user_id=str(internal_user_id),
                record_ids=[str(rid) for rid in created_ids],
                record_count=len(created_ids),
            )
            return {
                "status": "success",
                "activity_id": object_id,
                "record_ids": [str(rid) for rid in created_ids],
            }

        except IntegrityError:
            db.rollback()
            log_structured(
                logger,
                "info",
                "Strava activity already exists, skipping",
                provider="strava",
                action="webhook_duplicate_activity",
                activity_id=object_id,
                user_id=str(internal_user_id),
            )
            return {"status": "warning", "message": "Duplicate activity"}

        except ValidationError as e:
            log_structured(
                logger,
                "error",
                "Failed to parse Strava activity",
                provider="strava",
                action="webhook_validation_error",
                activity_id=object_id,
                user_id=str(internal_user_id),
                error=str(e),
            )
            return {"status": "error", "message": "Validation error"}

        except Exception as e:
            log_structured(
                logger,
                "error",
                "Error processing Strava activity",
                provider="strava",
                action="webhook_processing_error",
                activity_id=object_id,
                user_id=str(internal_user_id),
                error=str(e),
            )
            return {"status": "error", "message": "Processing error"}

    except Exception as e:
        log_structured(
            logger,
            "error",
            "Error processing Strava webhook",
            provider="strava",
            action="webhook_error",
            error=str(e),
        )
        return {"status": "error", "message": "Error processing webhook event"}
