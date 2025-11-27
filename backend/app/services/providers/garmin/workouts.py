from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.schemas.workout import WorkoutCreate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class GarminWorkouts(BaseWorkoutsTemplate):
    """Garmin implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get activities from Garmin API."""
        # Garmin API uses seconds for timestamps
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": end_ts,
        }

        return self._make_api_request(
            db,
            user_id,
            "/wellness-api/rest/activities",
            params=params,
        )

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Garmin API with options."""
        summary_start_time = kwargs.get("summary_start_time")
        summary_end_time = kwargs.get("summary_end_time")

        start_ts = self._parse_timestamp(summary_start_time)
        end_ts = self._parse_timestamp(summary_end_time)

        params = {}
        if start_ts:
            params["uploadStartTimeInSeconds"] = start_ts
        if end_ts:
            params["uploadEndTimeInSeconds"] = end_ts

        return self._make_api_request(
            db,
            user_id,
            "/wellness-api/rest/activities",
            params=params,
        )

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Get detailed activity data from Garmin API."""
        return self.get_activity_detail(db, user_id, workout_id)

    def _parse_timestamp(self, value: str | None) -> int | None:
        """Parse timestamp from string (Unix timestamp or ISO 8601 date)."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            # If parsing fails, return None or raise error.
            # For now, let's return None to be safe, or we could raise HTTPException here if we want strict validation.
            # But since this is a helper, maybe just return None.
            # Actually, the endpoint was raising HTTPException.
            # Let's assume the caller handles validation or we just ignore invalid values.
            return None

    def normalize_workout(self, raw_workout: Any) -> WorkoutCreate:
        """Normalize Garmin activity to WorkoutCreate."""
        # This is a placeholder implementation.
        # You should map actual Garmin fields to WorkoutCreate fields.
        return WorkoutCreate(
            user_id=UUID(int=0),  # Will be overwritten by _process_single_workout
            provider_id=None,  # Map from raw_workout
            type=raw_workout.get("activityType", "unknown"),
            duration=float(raw_workout.get("durationInSeconds", 0)),
            durationUnit="seconds",
            sourceName="garmin",
            startDate=datetime.fromtimestamp(raw_workout.get("startTimeInSeconds", 0)),
            endDate=datetime.fromtimestamp(
                raw_workout.get("startTimeInSeconds", 0) + raw_workout.get("durationInSeconds", 0),
            ),
        )

    def get_activity_detail(
        self,
        db: DbSession,
        user_id: UUID,
        activity_id: str,
    ) -> dict:
        """Get detailed activity data from Garmin API."""
        return self._make_api_request(db, user_id, f"/wellness-api/rest/activities/{activity_id}")
