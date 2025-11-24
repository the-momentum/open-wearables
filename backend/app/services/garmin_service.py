from logging import Logger, getLogger
from uuid import UUID

from app.config import settings
from app.database import DbSession
from app.services.base_workout_service import BaseWorkoutService


class GarminService(BaseWorkoutService):
    """Service for interacting with Garmin Health API."""

    def __init__(self, log: Logger):
        super().__init__(
            log,
            provider="garmin",
            api_base_url=settings.garmin_api_base_url,
        )

    def get_activities(
        self,
        db: DbSession,
        user_id: UUID,
        summary_start_time_in_seconds: int | None = None,
        summary_end_time_in_seconds: int | None = None,
    ) -> list[dict]:
        """Get activities from Garmin API using cached pull token from webhook.

        When webhook receives activity notification, it saves the pull token to Redis.
        This method retrieves that token and uses it to fetch activities.

        Args:
            db: Database session
            user_id: User ID
            summary_start_time_in_seconds: Start time as Unix timestamp
            summary_end_time_in_seconds: End time as Unix timestamp

        Returns:
            list[dict]: List of activities from Garmin API
        """
        import redis

        # Try to get cached pull token from Redis
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

        # First try: get callback URL for latest activity
        callback_url = redis_client.get(f"garmin_callback_url:{user_id}:latest")

        if callback_url:
            self.logger.info(f"Using cached callback URL for user {user_id}")
            import httpx

            try:
                response = httpx.get(callback_url, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                self.logger.warning(f"Cached callback URL failed: {str(e)}, falling back to token search")

        # Second try: find token for specific time range
        if summary_start_time_in_seconds and summary_end_time_in_seconds:
            token_key = f"garmin_pull_token:{user_id}:{summary_start_time_in_seconds}_{summary_end_time_in_seconds}"
            pull_token = redis_client.get(token_key)

            if pull_token:
                self.logger.info(f"Using cached pull token for user {user_id}")
                params = {
                    "uploadStartTimeInSeconds": summary_start_time_in_seconds,
                    "uploadEndTimeInSeconds": summary_end_time_in_seconds,
                    "token": pull_token,
                }
                # Use standard API endpoint with pull token
                return self._make_api_request(db, user_id, "/wellness-api/rest/activities", params=params)

        # Fallback: no cached token available
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=(
                "No cached Garmin data available. "
                "Please wait for webhook notification from Garmin after completing an activity."
            ),
        )

    def get_activity_detail(
        self,
        db: DbSession,
        user_id: UUID,
        activity_id: str,
    ) -> dict:
        """Get detailed activity data from Garmin API.

        Args:
            db: Database session
            user_id: User ID
            activity_id: Garmin activity ID

        Returns:
            dict: Detailed activity data
        """
        self.logger.info(f"Fetching activity {activity_id} for user {user_id} from Garmin API")
        return self._make_api_request(db, user_id, f"/wellness-api/rest/activities/{activity_id}")

    def get_activity_details(
        self,
        db: DbSession,
        user_id: UUID,
        upload_start_time_in_seconds: int,
        upload_end_time_in_seconds: int,
    ) -> list[dict]:
        """Get activity details for a time range from Garmin API.

        Args:
            db: Database session
            user_id: User ID
            upload_start_time_in_seconds: Upload start time as Unix timestamp
            upload_end_time_in_seconds: Upload end time as Unix timestamp

        Returns:
            list[dict]: List of detailed activities from Garmin API
        """
        params = {
            "uploadStartTimeInSeconds": upload_start_time_in_seconds,
            "uploadEndTimeInSeconds": upload_end_time_in_seconds,
        }

        self.logger.info(
            f"Fetching activity details for user {user_id} from Garmin API "
            f"(upload time range: {upload_start_time_in_seconds} - {upload_end_time_in_seconds})",
        )
        return self._make_api_request(
            db,
            user_id,
            "/wellness-api/rest/activityDetails",
            params=params,
        )

    def get_user_permissions(
        self,
        db: DbSession,
        user_id: UUID,
    ) -> list[str]:
        """Get user permissions from Garmin API.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            list[str]: List of permissions granted by the user
        """
        self.logger.info(f"Fetching user permissions for user {user_id} from Garmin API")
        return self._make_api_request(db, user_id, "/wellness-api/rest/user/permissions")


garmin_service = GarminService(log=getLogger(__name__))
