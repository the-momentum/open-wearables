from logging import Logger, getLogger
from uuid import UUID

from app.config import settings
from app.database import DbSession
from app.services.base_workout_service import BaseWorkoutService


class SuuntoService(BaseWorkoutService):
    """Service for interacting with Suunto API."""

    def __init__(self, log: Logger):
        extra_headers = {}
        if settings.suunto_subscription_key:
            extra_headers["Ocp-Apim-Subscription-Key"] = settings.suunto_subscription_key.get_secret_value()
        super().__init__(
            log,
            provider="suunto",
            api_base_url=settings.suunto_api_base_url,
            extra_headers=extra_headers,
        )

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        since: int = 0,
        limit: int = 50,
        offset: int = 0,
        filter_by_modification_time: bool = True,
    ) -> dict:
        """Get workouts from Suunto API.

        Args:
            db: Database session
            user_id: User ID
            since: Unix timestamp to get workouts since (default: 0 = all)
            limit: Maximum number of workouts to return (default: 50, max: 100)
            offset: Offset for pagination (default: 0)
            filter_by_modification_time: Filter by modification time instead of creation time

        Returns:
            dict: Suunto API response with workouts list
        """
        params = {
            "since": since,
            "limit": min(limit, 100),  # Suunto max is 100
            "offset": offset,
            "filter-by-modification-time": str(filter_by_modification_time).lower(),
        }

        self.logger.info(f"Fetching workouts for user {user_id} from Suunto API")
        return self._make_api_request(db, user_id, "/v3/workouts/", params=params)

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API.

        Args:
            db: Database session
            user_id: User ID
            workout_key: Suunto workout key/ID

        Returns:
            dict: Detailed workout data
        """
        self.logger.info(f"Fetching workout {workout_key} for user {user_id} from Suunto API")
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}")


suunto_service = SuuntoService(log=getLogger(__name__))
