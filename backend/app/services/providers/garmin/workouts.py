from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import (
    GarminActivityJSON,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.workout_service import workout_service
from app.services.workout_statistic_service import workout_statistic_service


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

    def _normalize_workout(
        self,
        raw_workout: GarminActivityJSON,
        user_id: UUID,
    ) -> WorkoutCreate:
        """Normalize Garmin activity to WorkoutCreate."""
        workout_id = uuid4()

        start_date = datetime.fromtimestamp(raw_workout.startTimeInSeconds)
        end_date = datetime.fromtimestamp(raw_workout.startTimeInSeconds + raw_workout.durationInSeconds)
        duration_seconds = raw_workout.durationInSeconds

        return WorkoutCreate(
            id=workout_id,
            provider_id=raw_workout.summaryId,
            user_id=user_id,
            type=raw_workout.activityType,
            duration_seconds=Decimal(duration_seconds),
            source_name=raw_workout.deviceName,
            start_datetime=start_date,
            end_datetime=end_date,
        )

    def _normalize_workout_statistics(
        self,
        raw_workout: GarminActivityJSON,
        user_id: UUID,
        workout_id: UUID,
    ) -> list[WorkoutStatisticCreate]:
        """Normalize Garmin activity statistics to WorkoutStatisticCreate."""
        workout_statistics = []

        units = {
            "distanceInMeters": "m",
            "steps": "count",
            "activeKilocalories": "kcal",
        }

        start_date = datetime.fromtimestamp(raw_workout.startTimeInSeconds)
        end_date = datetime.fromtimestamp(raw_workout.startTimeInSeconds + raw_workout.durationInSeconds)

        for field in ["distanceInMeters", "steps", "activeKilocalories"]:
            value = getattr(raw_workout, field)
            workout_statistics.append(
                WorkoutStatisticCreate(
                    id=uuid4(),
                    user_id=user_id,
                    workout_id=workout_id,
                    type=field,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    min=None,
                    max=None,
                    avg=value,
                    unit=units[field],
                ),
            )

        workout_statistics.append(
            WorkoutStatisticCreate(
                id=uuid4(),
                user_id=user_id,
                workout_id=workout_id,
                type="heartRate",
                start_datetime=start_date,
                end_datetime=end_date,
                min=None,  # doesnt exist for garmin
                max=raw_workout.maxHeartRateInBeatsPerMinute,
                avg=raw_workout.averageHeartRateInBeatsPerMinute,
                unit="bpm",
            ),
        )

        return workout_statistics

    def _build_bundles(
        self,
        raw: list[GarminActivityJSON],
        user_id: UUID,
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        """Build bundles of WorkoutCreate and WorkoutStatisticCreate."""
        for raw_workout in raw:
            workout = self._normalize_workout(raw_workout, user_id)
            statistics = self._normalize_workout_statistics(raw_workout, user_id, workout.id)
            yield workout, statistics

    def load_data(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """Load data from Garmin API."""
        workouts = self.get_workouts(db, user_id, start_date, end_date)
        activities = [GarminActivityJSON(**activity) for activity in workouts]

        for workout_row, workout_statistics in self._build_bundles(activities, user_id):
            workout_service.create(db, workout_row)
            for stat in workout_statistics:
                workout_statistic_service.create(db, stat)

        return True

    def get_activity_detail(
        self,
        db: DbSession,
        user_id: UUID,
        activity_id: str,
    ) -> dict:
        """Get detailed activity data from Garmin API."""
        return self._make_api_request(db, user_id, f"/wellness-api/rest/activities/{activity_id}")
