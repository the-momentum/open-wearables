from datetime import datetime
from logging import Logger, getLogger
from typing import Iterable
from uuid import uuid4

from app.services.apple.workout_service import workout_service
from app.services.apple.workout_statistic_service import workout_statistic_service
from app.schemas import (
    SuuntoRootJSON,
    SuuntoWorkoutJSON,
    SuuntoHeartRateJSON,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.database import DbSession


class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.workout_service = workout_service
        self.workout_statistic_service = workout_statistic_service

    def _build_bundles(self, raw: list[SuuntoWorkoutJSON], user_id: str) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        for raw_workout in raw:
            workout = SuuntoWorkoutJSON(**raw_workout)
            
            workout_id = uuid4()
            
            start_date = datetime.fromtimestamp(workout.startTime / 1000)
            end_date = datetime.fromtimestamp(workout.stopTime / 1000)
            duration = workout.totalTime / 60
            duration_unit = "min"
            
            device_data = workout.gear
            sourceName = device_data.name
            
            workout_row = WorkoutCreate(
                id=workout_id,
                provider_id=workout.workoutId,
                user_id=user_id,
                type=workout.name,
                duration=duration,
                durationUnit=duration_unit,
                sourceName=sourceName,
                startDate=start_date,
                endDate=end_date,
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
                        sourceName=sourceName,
                        startDate=start_date,
                        endDate=end_date,
                        min=value,
                        max=value,
                        avg=value,
                        unit=units[field],
                    )
                )
                
            hr_data = SuuntoHeartRateJSON(**workout.hrdata)
            workout_statistics.append(
                WorkoutStatisticCreate(
                    id=uuid4(),
                    user_id=user_id,
                    workout_id=workout_id,
                    type="heartRate",
                    sourceName=sourceName,
                    startDate=start_date,
                    endDate=end_date,
                    min=None, # doesnt exist for suunto
                    max=hr_data.max,
                    avg=hr_data.avg,
                    unit="bpm",
                )
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
        
suunto_import_service = ImportService(log=getLogger(__name__))