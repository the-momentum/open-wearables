from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import (
    SuuntoWorkoutJSON,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.workout_service import workout_service
from app.services.workout_statistic_service import workout_statistic_service


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

    def _normalize_workout(
        self,
        raw_workout: SuuntoWorkoutJSON,
        user_id: UUID,
    ) -> WorkoutCreate:
        """Normalize Suunto workout to WorkoutCreate."""
        workout_id = uuid4()

        start_date = datetime.fromtimestamp(raw_workout.startTime / 1000)
        end_date = datetime.fromtimestamp(raw_workout.stopTime / 1000)
        duration_seconds = raw_workout.totalTime

        source_name = raw_workout.gear.name if raw_workout.gear else "Unknown"

        return WorkoutCreate(
            id=workout_id,
            provider_id=str(raw_workout.workoutId),
            user_id=user_id,
            type="Unknown",
            duration_seconds=Decimal(duration_seconds),
            source_name=source_name,
            start_datetime=start_date,
            end_datetime=end_date,
        )

    def _normalize_workout_statistics(
        self,
        raw_workout: SuuntoWorkoutJSON,
        user_id: UUID,
        workout_id: UUID,
    ) -> list[WorkoutStatisticCreate]:
        """Normalize Suunto workout statistics to WorkoutStatisticCreate."""
        workout_statistics = []

        units = {
            "totalDistance": "km",
            "stepCount": "count",
            "energyConsumption": "kcal",
        }

        start_date = datetime.fromtimestamp(raw_workout.startTime / 1000)
        end_date = datetime.fromtimestamp(raw_workout.stopTime / 1000)

        for field in ["totalDistance", "stepCount", "energyConsumption"]:
            value = getattr(raw_workout, field)
            workout_statistics.append(
                WorkoutStatisticCreate(
                    id=uuid4(),
                    user_id=user_id,
                    workout_id=workout_id,
                    type=field,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    min=value,
                    max=value,
                    avg=value,
                    unit=units[field],
                ),
            )

        hr_data = raw_workout.hrdata
        if hr_data:
            workout_statistics.append(
                WorkoutStatisticCreate(
                    id=uuid4(),
                    user_id=user_id,
                    workout_id=workout_id,
                    type="heartRate",
                    start_datetime=start_date,
                    end_datetime=end_date,
                    min=None,  # doesnt exist for suunto
                    max=hr_data.max,
                    avg=hr_data.avg,
                    unit="bpm",
                ),
            )

        return workout_statistics

    def _build_bundles(
        self,
        raw: list[SuuntoWorkoutJSON],
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
        """Load data from Suunto API."""
        workouts_data = self.get_workouts(db, user_id, start_date, end_date)
        workouts = [SuuntoWorkoutJSON(**w) for w in workouts_data]

        for workout_row, workout_statistics in self._build_bundles(workouts, user_id):
            workout_service.create(db, workout_row)
            for stat in workout_statistics:
                workout_statistic_service.create(db, stat)

        return True

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API."""
        headers = self._get_suunto_headers()
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}", headers=headers)
