import json
from logging import Logger, getLogger
from typing import Iterable
from uuid import uuid4

from app.database import DbSession
from app.schemas import (
    HKRecordJSON,
    HKWorkoutJSON,
    RootJSON,
    UploadDataResponse,
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

    def _build_workout_bundles(
        self,
        raw: dict,
        user_id: str,
    ) -> Iterable[tuple[WorkoutCreate, list[WorkoutStatisticCreate]]]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield ImportBundle(s)
        ready to insert into your ORM session.
        """
        root = RootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])
        for w in workouts_raw:
            wjson = HKWorkoutJSON(**w)

            provider_id = wjson.uuid if wjson.uuid else None

            duration_seconds = (wjson.endDate - wjson.startDate).total_seconds()

            workout_create = WorkoutCreate(
                id=uuid4(),
                provider_id=provider_id,
                user_id=user_id,
                type=wjson.type or "Unknown",
                duration_seconds=duration_seconds,
                source_name=wjson.sourceName or "Apple Health",
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
            )

            # Handle workout statistics
            workout_statistics = []
            if wjson.workoutStatistics is not None:
                for stat in wjson.workoutStatistics:
                    stat_create = WorkoutStatisticCreate(
                        id=uuid4(),
                        user_id=user_id,
                        workout_id=workout_create.id,
                        type=stat.type,
                        start_datetime=wjson.startDate,
                        end_datetime=wjson.endDate,
                        min=stat.value,
                        max=stat.value,
                        avg=stat.value,
                        unit=stat.unit,
                    )
                    workout_statistics.append(stat_create)

            yield workout_create, workout_statistics

    def _build_statistic_bundles(self, raw: dict, user_id: str) -> Iterable[tuple[WorkoutStatisticCreate]]:
        root = RootJSON(**raw)
        records_raw = root.data.get("records", [])
        for r in records_raw:
            rjson = HKRecordJSON(**r)

            provider_id = rjson.uuid if rjson.uuid else None

            stat_create = WorkoutStatisticCreate(
                id=uuid4(),
                provider_id=provider_id,
                user_id=user_id,
                type=rjson.type or "Unknown",
                start_datetime=rjson.startDate,
                end_datetime=rjson.endDate,
                unit=rjson.unit,
                min=rjson.value,
                max=rjson.value,
                avg=rjson.value,
            )

            yield stat_create

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        for workout_row, workout_statistics in self._build_workout_bundles(raw, user_id):
            self.workout_service.create(db_session, workout_row)

            for stat_create in workout_statistics:
                self.workout_statistic_service.create(db_session, stat_create)

        for stat_create in self._build_statistic_bundles(raw, user_id):
            self.workout_statistic_service.create(db_session, stat_create)

        return True

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
