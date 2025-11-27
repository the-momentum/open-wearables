from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.schemas.workout import WorkoutCreate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class PolarWorkouts(BaseWorkoutsTemplate):
    """Polar implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get exercises from Polar API."""
        return self._make_api_request(db, user_id, "/v3/exercises")

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get exercises from Polar API with options."""
        samples = kwargs.get("samples", False)
        zones = kwargs.get("zones", False)
        route = kwargs.get("route", False)

        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }
        return self._make_api_request(db, user_id, "/v3/exercises", params=params)

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed exercise data from Polar API."""
        samples = kwargs.get("samples", False)
        zones = kwargs.get("zones", False)
        route = kwargs.get("route", False)
        return self.get_exercise_detail(db, user_id, workout_id, samples, zones, route)

    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Normalize Polar exercise to WorkoutCreate."""
        # Placeholder mapping
        return WorkoutCreate(
            user_id=UUID(int=0),
            provider_id=None,
            type=raw_workout.get("sport", "unknown"),
            duration=float(
                raw_workout.get("duration", "PT0S").replace("PT", "").replace("S", ""),
            ),  # ISO duration parsing needed properly
            durationUnit="seconds",
            sourceName="polar",
            startDate=datetime.fromisoformat(raw_workout.get("startTime", datetime.now().isoformat())),
            endDate=datetime.now(),  # Calculate from duration
        )

    def get_exercise_detail(
        self,
        db: DbSession,
        user_id: UUID,
        exercise_id: str,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> dict:
        """Get detailed exercise data from Polar API."""
        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }
        return self._make_api_request(db, user_id, f"/v3/exercises/{exercise_id}", params=params)
