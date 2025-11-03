import json
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Iterable
from logging import Logger, getLogger

from app.database import DbSession
from app.services.apple.healthkit.workout_service import workout_service
from app.services.apple.healthkit.workout_statistic_service import workout_statistic_service
from app.services.apple.healthkit.record_service import record_service
# from app.services.apple.healthkit.metadata_entry_service import metadata_entry_service
from app.schemas import (
    HKRootJSON,
    HKWorkoutJSON,
    HKWorkoutIn,
    HKWorkoutCreate,
    HKWorkoutStatisticCreate,
    HKWorkoutStatisticIn,
    HKRecordJSON,
    HKRecordIn,
    HKMetadataEntryIn,
    HKRecordCreate,
    # HKMetadataEntryCreate,
    UploadDataResponse,
)


class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.workout_service = workout_service
        self.workout_statistic_service = workout_statistic_service
        self.record_service = record_service
        # self.metadata_entry_service = metadata_entry_service
        
    def _build_workout_bundles(self, raw: dict, user_id: str) -> Iterable[tuple[HKWorkoutIn, list[HKWorkoutStatisticIn]]]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield ImportBundle(s)
        ready to insert into your ORM session.
        """
        root = HKRootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])
        for w in workouts_raw:
            wjson = HKWorkoutJSON(**w)

            # prioritize id from json
            provider_id = wjson.uuid if wjson.uuid else uuid4()
            # first user_id from token -> json -> default to None
            user_id = user_id if user_id else (wjson.user_id if wjson.user_id else None)

            duration = (wjson.endDate - wjson.startDate).total_seconds() / 60

            workout_row = HKWorkoutIn(
                id=uuid4(),
                provider_id=provider_id,
                user_id=user_id,
                type=wjson.type,
                startDate=wjson.startDate,
                endDate=wjson.endDate,
                duration=Decimal(str(duration)),
                durationUnit="min",
                sourceName=wjson.sourceName,
            )

            # Handle workout statistics
            workout_statistics = []
            if wjson.workoutStatistics is not None:
                for stat in wjson.workoutStatistics:
                    stat_in = HKWorkoutStatisticIn(
                        type=stat.type,
                        value=stat.value,
                        unit=stat.unit
                    )
                    workout_statistics.append(stat_in)

            yield workout_row, workout_statistics
            
    def _build_record_bundles(self, raw: dict, user_id: str) -> Iterable[tuple[HKRecordIn, list[HKMetadataEntryIn]]]:
        root = HKRootJSON(**raw)
        records_raw = root.data.get("records", [])
        for r in records_raw:
            rjson = HKRecordJSON(**r)
            
            provider_id = UUID(rjson.uuid) if rjson.uuid else None
            # first user_id from token -> json -> default to None
            user_id = user_id if user_id else (rjson.user_id if rjson.user_id else None)
            
            record_row = HKRecordIn(
                id=uuid4(),
                provider_id=provider_id,
                user_id=user_id,
                type=rjson.type,
                startDate=rjson.startDate,
                endDate=rjson.endDate,
                unit=rjson.unit, 
                value=rjson.value,
                sourceName=rjson.sourceName,
            )
            
            record_metadata = []
            if rjson.recordMetadata is not None:
                for metadata in rjson.recordMetadata:
                    metadata_in = HKMetadataEntryIn(
                        key=metadata.get("key", ""),
                        value=Decimal(str(metadata.get("value", 0))),
                    )
                    record_metadata.append(metadata_in)
                    
            yield record_row, record_metadata

    def load_data(self, db_session: DbSession, raw: dict, user_id: str = None) -> bool:
        for workout_row, workout_statistics in self._build_workout_bundles(raw, user_id):
            workout_data = workout_row.model_dump()
            if user_id:
                workout_data['user_id'] = UUID(user_id)
            workout_create = HKWorkoutCreate(**workout_data)
            created_workout = self.workout_service.create(db_session, workout_create)
            
            # Create workout statistics
            for stat_in in workout_statistics:
                stat_create = HKWorkoutStatisticCreate(
                    user_id=created_workout.user_id,
                    workout_id=created_workout.id,
                    type=stat_in.type,
                    value=stat_in.value,
                    unit=stat_in.unit
                )
                self.workout_statistic_service.create(db_session, stat_create)

        for record_row, record_metadata in self._build_record_bundles(raw, user_id):
            record_data = record_row.model_dump()
            if user_id:
                record_data['user_id'] = UUID(user_id)
            record_create = HKRecordCreate(**record_data)
            created_record = self.record_service.create(db_session, record_create)
            
            # # Create record metadata
            # for metadata_in in record_metadata:
            #     metadata_create = HKMetadataEntryCreate(
            #         user_id=created_record.user_id,
            #         record_id=created_record.id,
            #         type=metadata_in.type,
            #         value=metadata_in.value,
            #     )
            #     self.metadata_entry_service.create(db_session, metadata_create)

        return True

    async def import_data_from_request(
            self,
            db_session: DbSession,
            request_content: str,
            content_type: str,
            user_id: str
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
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break

        if brace_count != 0:
            return None

        json_str = content[json_start:json_end + 1]
        return json.loads(json_str)

    def _parse_json_content(self, content: str) -> dict | None:
        """Parse JSON content directly."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


import_service = ImportService(log=getLogger(__name__))
