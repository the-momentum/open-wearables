from datetime import datetime
from logging import Logger, getLogger
from typing import Iterable
from uuid import uuid4

from app.database import DbSession
from app.schemas import (
    GarminActivityJSON,
    GarminRootJSON,
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
        self, raw: list[GarminActivityJSON], user_id: str
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        for activity in raw:
            workout_id = uuid4()

            start_date = datetime.fromtimestamp(activity.startTimeInSeconds)
            end_date = datetime.fromtimestamp(activity.startTimeInSeconds + activity.durationInSeconds)
            duration_seconds = activity.durationInSeconds

            workout_row = WorkoutCreate(
                id=workout_id,
                provider_id=activity.summaryId,
                user_id=user_id,
                type=activity.activityType,
                duration_seconds=duration_seconds,
                source_name=activity.deviceName,
                start_datetime=start_date,
                end_datetime=end_date,
            )

            workout_statistics = []

            units = {
                "distanceInMeters": "m",
                "steps": "count",
                "activeKilocalories": "kcal",
            }

            for field in ["distanceInMeters", "steps", "activeKilocalories"]:
                value = getattr(activity, field)
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
                    max=activity.maxHeartRateInBeatsPerMinute,
                    avg=activity.averageHeartRateInBeatsPerMinute,
                    unit="bpm",
                ),
            )

            yield workout_row, workout_statistics

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        root = GarminRootJSON(**raw)
        if root.error:
            raise ValueError(root.error)

        raw_activities = root.activities

        for workout_row, workout_statistics in self._build_bundles(raw_activities, user_id):
            self.workout_service.create(db_session, workout_row)
            for stat in workout_statistics:
                self.workout_statistic_service.create(db_session, stat)

        return True


import_service = ImportService(log=getLogger(__name__))
