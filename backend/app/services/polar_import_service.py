from datetime import datetime, timedelta
from logging import Logger, getLogger
from typing import Iterable
from uuid import uuid4

import isodate

from app.database import DbSession
from app.schemas import (
    PolarExerciseJSON,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.services.workout_service import workout_service
from app.services.workout_statistic_service import workout_statistic_service


class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.workout_service = workout_service
        self.workout_statistic_service = workout_statistic_service

    def _build_bundles(
        self, raw: list[PolarExerciseJSON], user_id: str
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        for exercise in raw:
            workout_id = uuid4()

            start_date: datetime = isodate.parse_datetime(exercise.start_time)
            offset: timedelta = timedelta(minutes=exercise.start_time_utc_offset)
            start_date: datetime = start_date + offset
            end_date: datetime = start_date + timedelta(seconds=exercise.duration)

            hr_avg = exercise.heart_rate.average
            hr_max = exercise.heart_rate.maximum

            workout_row = WorkoutCreate(
                id=workout_id,
                provider_id=exercise.id,
                user_id=user_id,
                type=exercise.sport,
                duration_seconds=exercise.duration,
                source_name=exercise.device,
                start_datetime=start_date,
                end_datetime=end_date,
            )

            units = {
                "calories": "kcal",
                "distance": "m",
            }

            workout_statistics = []

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
                        avg=getattr(exercise, field),
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
                    min=None,
                    max=hr_max,
                    avg=hr_avg,
                    unit="bpm",
                ),
            )

            yield workout_row, workout_statistics

    def load_data(self, db_session: DbSession, raw: list[dict], user_id: str) -> bool:
        raw_exercises = [PolarExerciseJSON(**exercise) for exercise in raw]

        for exercise_row, exercise_statistics in self._build_bundles(raw_exercises, user_id):
            self.workout_service.create(db_session, exercise_row)
            for stat in exercise_statistics:
                self.workout_statistic_service.create(db_session, stat)

        return True


import_service = ImportService(log=getLogger(__name__))
