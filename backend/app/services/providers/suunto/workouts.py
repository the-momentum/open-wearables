from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas.workout import WorkoutCreate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class SuuntoWorkouts(BaseWorkoutsTemplate):
    """Suunto implementation of workouts template."""

    def _get_suunto_headers(self) -> dict[str, str]:
        """Get Suunto-specific headers including subscription key."""
        headers = {}
        if self.oauth and hasattr(self.oauth, "credentials"):
            subscription_key = self.oauth.credentials.subscription_key
            if subscription_key:
                headers["Ocp-Apim-Subscription-Key"] = subscription_key
        return headers

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
        headers = self._get_suunto_headers()
        response = self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)
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

        # Suunto requires subscription key header
        headers = self._get_suunto_headers()

        return self._make_api_request(db, user_id, "/v3/workouts/", params=params, headers=headers)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed workout data from Suunto API."""
        return self.get_workout_detail(db, user_id, workout_id)

    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Normalize Suunto workout to WorkoutCreate."""
        # Placeholder mapping
        return WorkoutCreate(
            id=uuid4(),
            user_id=UUID(int=0),
            provider_id=None,
            type=str(raw_workout.get("activityId", "unknown")),
            duration_seconds=Decimal(raw_workout.get("totalTime", 0)),
            source_name="suunto",
            start_datetime=datetime.fromisoformat(raw_workout.get("startTime", datetime.now().isoformat())),
            end_datetime=datetime.fromisoformat(raw_workout.get("stopTime", datetime.now().isoformat())),
        )

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API."""
        headers = self._get_suunto_headers()
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}", headers=headers)
