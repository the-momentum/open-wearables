from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

import isodate

from app.database import DbSession
from app.schemas import (
    PolarExerciseJSON,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.workout_service import workout_service
from app.services.workout_statistic_service import workout_statistic_service


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

    def _extract_dates(self, start_timestamp: Any, end_timestamp: Any) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps.

        Note: Polar uses a different format with offset, so this delegates to _extract_dates_with_offset.
        This is required by the base template but not used directly.
        """
        raise NotImplementedError("Use _extract_dates_with_offset for Polar workouts")

    def _extract_dates_with_offset(
        self,
        start_time: str,
        start_time_utc_offset: int,
        duration: str,
    ) -> tuple[datetime, datetime]:
        """Extract start and end dates from timestamps with UTC offset."""
        start_date = isodate.parse_datetime(start_time)
        offset = timedelta(minutes=start_time_utc_offset)
        start_date = start_date + offset
        duration_td = isodate.parse_duration(duration)
        end_date = start_date + duration_td
        return start_date, end_date

    def _normalize_workout(
        self,
        raw_workout: PolarExerciseJSON,
        user_id: UUID,
    ) -> WorkoutCreate:
        """Normalize Polar exercise to WorkoutCreate."""
        workout_id = uuid4()

        start_date, end_date = self._extract_dates_with_offset(
            raw_workout.start_time,
            raw_workout.start_time_utc_offset,
            raw_workout.duration,
        )
        duration_seconds = (end_date - start_date).total_seconds()

        return WorkoutCreate(
            id=workout_id,
            provider_id=raw_workout.id,
            user_id=user_id,
            type=raw_workout.sport,
            duration_seconds=Decimal(duration_seconds),
            source_name=raw_workout.device,
            start_datetime=start_date,
            end_datetime=end_date,
        )

    def _normalize_workout_statistics(
        self,
        raw_workout: PolarExerciseJSON,
        user_id: UUID,
        workout_id: UUID,
    ) -> list[WorkoutStatisticCreate]:
        """Normalize Polar exercise statistics to WorkoutStatisticCreate."""
        workout_statistics = []

        start_date, end_date = self._extract_dates_with_offset(
            raw_workout.start_time,
            raw_workout.start_time_utc_offset,
            raw_workout.duration,
        )

        units = {
            "calories": "kcal",
            "distance": "m",
        }

        for field in ["calories", "distance"]:
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
                    avg=getattr(raw_workout, field),
                    unit=units[field],
                ),
            )

        hr_avg = raw_workout.heart_rate.average
        hr_max = raw_workout.heart_rate.maximum

        workout_statistics.append(
            WorkoutStatisticCreate(
                id=uuid4(),
                user_id=user_id,
                workout_id=workout_id,
                type="heartRate",
                start_datetime=start_date,
                end_datetime=end_date,
                min=None,
                max=hr_max,
                avg=hr_avg,
                unit="bpm",
            ),
        )

        return workout_statistics

    def _build_bundles(
        self,
        raw: list[PolarExerciseJSON],
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
        **kwargs: Any,
    ) -> bool:
        """Load data from Polar API."""
        workouts_data = self.get_workouts_from_api(db, user_id, **kwargs)
        workouts = [PolarExerciseJSON(**w) for w in workouts_data]

        for workout_row, workout_statistics in self._build_bundles(workouts, user_id):
            workout_service.create(db, workout_row)
            for stat in workout_statistics:
                workout_statistic_service.create(db, stat)

        return True

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
