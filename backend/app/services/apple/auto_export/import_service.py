import json
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import (
    AEWorkoutJSON,
    RootJSON,
    UploadDataResponse,
    WorkoutCreate,
    WorkoutStatisticCreate,
)
from app.services.workout_service import workout_service
from app.services.workout_statistic_service import workout_statistic_service
from app.utils.exceptions import handle_exceptions

APPLE_DT_FORMAT = "%Y-%m-%d %H:%M:%S %z"


class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.workout_service = workout_service
        self.workout_statistic_service = workout_statistic_service

    def _dt(self, s: str) -> datetime:
        s = s.replace(" +", "+").replace(" ", "T", 1)
        if len(s) >= 5 and (s[-5] in {"+", "-"} and s[-3] != ":"):
            s = f"{s[:-2]}:{s[-2:]}"
        return datetime.fromisoformat(s)

    def _dec(self, x: float | int | None) -> Decimal | None:
        return None if x is None else Decimal(str(x))

    def _get_workout_statistics(
        self, workout: AEWorkoutJSON, user_id: str, workout_id: UUID
    ) -> list[WorkoutStatisticCreate]:
        """
        Get workout statistics from workout JSON.
        """
        statistics: list[WorkoutStatisticCreate] = []

        for field in ["activeEnergyBurned", "distance", "intensity", "temperature", "humidity"]:
            if field in workout:
                data = getattr(workout, field)
                statistics.append(
                    WorkoutStatisticCreate(
                        id=uuid4(),
                        user_id=UUID(user_id),
                        workout_id=workout_id,
                        type=field,
                        start_datetime=workout.start,
                        end_datetime=workout.end,
                        min=data.qty or 0,
                        max=data.qty or 0,
                        avg=data.qty or 0,
                        unit=data.units or "",
                    ),
                )

        return statistics

    def _get_records(
        self,
        workout: AEWorkoutJSON,
        workout_id: UUID,
        user_id: str,
    ) -> tuple[list[WorkoutStatisticCreate]]:
        statistics: list[WorkoutStatisticCreate] = []

        for field in ["heartRate", "heartRateRecovery", "activeEnergy"]:
            if field in workout:
                data = getattr(workout, field)
                for entry in data:
                    statistics.append(
                        WorkoutStatisticCreate(
                            id=uuid4(),
                            user_id=UUID(user_id),
                            workout_id=workout_id,
                            type=field,
                            start_datetime=self._dt(entry.date),
                            end_datetime=self._dt(entry.date),
                            min=entry.min or 0,
                            max=entry.max or 0,
                            avg=entry.avg or 0,
                            unit=entry.units or "",
                        ),
                    )

        return statistics

    def _build_import_bundles(
        self, raw: dict, user_id: str
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield ImportBundles
        ready to insert the database.
        """
        root = RootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])

        for w in workouts_raw:
            wjson = AEWorkoutJSON(**w)

            workout_id = uuid4()

            start_date = self._dt(wjson.start)
            end_date = self._dt(wjson.end)
            duration_seconds = (end_date - start_date).total_seconds()

            workout_statistics = self._get_workout_statistics(wjson, user_id, workout_id)
            records = self._get_records(wjson, workout_id, user_id)

            statistics = [*workout_statistics, *records]

            workout_type = wjson.name or "Unknown Workout"

            workout_row = WorkoutCreate(
                id=workout_id,
                user_id=UUID(user_id),
                type=workout_type,
                duration_seconds=duration_seconds,
                source_name="Auto Export",
                start_datetime=start_date,
                end_datetime=end_date,
            )

            yield workout_row, statistics

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        for workout_row, statistics in self._build_import_bundles(raw, user_id):
            self.workout_service.create(db_session, workout_row)

            for stat in statistics:
                self.workout_statistic_service.create(db_session, stat)

        return True

    @handle_exceptions
    async def import_data_from_request(
        self,
        db_session: DbSession,
        request_content: str,
        content_type: str,
        user_id: str,
    ) -> UploadDataResponse:
        try:
            # Parse content based on type
            if "multipart/form-data" in content_type:
                data = self._parse_multipart_content(request_content)
            else:
                data = self._parse_json_content(request_content)

            if not data:
                return UploadDataResponse(status_code=400, response="No valid data found")

            # Load data using provided database session
            self.load_data(db_session, data, user_id=user_id)

        except Exception as e:
            return UploadDataResponse(status_code=400, response=f"Import failed: {str(e)}")

        return UploadDataResponse(status_code=200, response="Import successful")

    def _parse_multipart_content(self, content: str) -> dict | None:
        """Parse multipart form data to extract JSON."""
        json_start = content.find('{\n  "data"')
        if json_start == -1:
            json_start = content.find('{"data"')
        if json_start == -1:
            return None

        brace_count = 0
        json_end = json_start
        for i, char in enumerate(content[json_start:], json_start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break

        if brace_count != 0:
            return None

        json_str = content[json_start : json_end + 1]
        return json.loads(json_str)

    def _parse_json_content(self, content: str) -> dict | None:
        """Parse JSON content directly."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


import_service = ImportService(log=getLogger(__name__))
