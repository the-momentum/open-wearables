from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.schemas.workout import WorkoutCreate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class SuuntoWorkouts(BaseWorkoutsTemplate):
    """Suunto implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get workouts from Suunto API."""
        # Suunto uses 'since' parameter
        since = int(start_date.timestamp())
        params = {
            "since": since,
            "limit": 100,
        }
        response = self._make_api_request(db, user_id, "/v3/workouts/", params=params)
        return response.get("payload", [])

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get workouts from Suunto API with specific options."""
        since = kwargs.get("since", 0)
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)
        filter_by_modification_time = kwargs.get("filter_by_modification_time", True)

        params = {
            "since": since,
            "limit": min(limit, 100),
            "offset": offset,
            "filter-by-modification-time": str(filter_by_modification_time).lower(),
        }
        return self._make_api_request(db, user_id, "/v3/workouts/", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Suunto API."""
        return self.get_workout_detail(db, user_id, workout_id)

    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Normalize Suunto workout to WorkoutCreate."""
        # Placeholder mapping
        return WorkoutCreate(
            user_id=UUID(int=0),
            provider_id=None,
            type=str(raw_workout.get("activityId", "unknown")),
            duration=float(raw_workout.get("totalTime", 0)),
            durationUnit="seconds",
            sourceName="suunto",
            startDate=datetime.fromisoformat(raw_workout.get("startTime", datetime.now().isoformat())),
            endDate=datetime.fromisoformat(raw_workout.get("stopTime", datetime.now().isoformat())),
        )

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API."""
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}")
