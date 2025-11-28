from datetime import datetime
from logging import Logger, getLogger
from typing import Iterable
from uuid import uuid4

from app.database import DbSession
from app.schemas import (
    SuuntoRootJSON,
    SuuntoWorkoutJSON,
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
        self, raw: list[SuuntoWorkoutJSON], user_id: str
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        for workout in raw:
            workout_id = uuid4()

            start_date = datetime.fromtimestamp(workout.startTime / 1000)
            end_date = datetime.fromtimestamp(workout.stopTime / 1000)
            duration_seconds = workout.totalTime

            if workout.gear:
                source_name = workout.gear.name
            else:
                source_name = "Unknown"

            workout_row = WorkoutCreate(
                id=workout_id,
                provider_id=str(workout.workoutId),
                user_id=user_id,
                type="Unknown",
                duration_seconds=duration_seconds,
                source_name=source_name,
                start_datetime=start_date,
                end_datetime=end_date,
            )

            workout_statistics = []

            units = {
                "totalDistance": "km",
                "stepCount": "count",
                "energyConsumption": "kcal",
            }

            for field in ["totalDistance", "stepCount", "energyConsumption"]:
                value = getattr(workout, field)
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

            hr_data = workout.hrdata
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

            yield workout_row, workout_statistics

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        root = SuuntoRootJSON(**raw)
        if root.error:
            raise ValueError(root.error)

        raw_workouts = root.payload

        for workout_row, workout_statistics in self._build_bundles(raw_workouts, user_id):
            self.workout_service.create(db_session, workout_row)
            for stat in workout_statistics:
                self.workout_statistic_service.create(db_session, stat)

        return True


import_service = ImportService(log=getLogger(__name__))
