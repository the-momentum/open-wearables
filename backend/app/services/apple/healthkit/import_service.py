import json
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    HKRecordJSON,
    HKWorkoutJSON,
    RootJSON,
    StepSampleCreate,
    UploadDataResponse,
)
from app.services.event_record_service import event_record_service
from app.services.time_series_service import time_series_service


class ImportService:
    def __init__(self, log: Logger):
        self.log = log
        self.event_record_service = event_record_service
        self.time_series_service = time_series_service

    def _dec(self, value: float | int | Decimal | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def _build_workout_bundles(
        self,
        raw: dict,
        user_id: str,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield tuples of
        (EventRecordCreate, EventRecordDetailCreate) ready to insert into your ORM session.
        """
        root = RootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])
        user_uuid = UUID(user_id)
        for w in workouts_raw:
            wjson = HKWorkoutJSON(**w)

            workout_id = uuid4()
            provider_id = wjson.uuid if wjson.uuid else None

            duration_seconds = int((wjson.endDate - wjson.startDate).total_seconds())

            metrics = self._extract_metrics_from_workout_stats(wjson.workoutStatistics)

            record = EventRecordCreate(
                category="workout",
                type=wjson.type or "Unknown",
                source_name=wjson.sourceName or "Apple Health",
                device_id=wjson.sourceName or None,
                duration_seconds=duration_seconds,
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
                id=workout_id,
                provider_id=provider_id,
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail

    def _build_statistic_bundles(
        self,
        raw: dict,
        user_id: str,
    ) -> Iterable[tuple[list[HeartRateSampleCreate], list[StepSampleCreate]]]:
        root = RootJSON(**raw)
        records_raw = root.data.get("records", [])
        heart_rate_samples: list[HeartRateSampleCreate] = []
        step_samples: list[StepSampleCreate] = []
        user_uuid = UUID(user_id)

        for r in records_raw:
            rjson = HKRecordJSON(**r)
            value = Decimal(str(rjson.value))

            record_type = rjson.type or ""
            if "HeartRate" in record_type:
                heart_rate_samples.append(
                    HeartRateSampleCreate(
                        id=uuid4(),
                        user_id=user_uuid,
                        provider_id=rjson.uuid,
                        device_id=rjson.sourceName or None,
                        recorded_at=rjson.startDate,
                        value=value,
                    ),
                )
            elif "StepCount" in record_type:
                step_samples.append(
                    StepSampleCreate(
                        id=uuid4(),
                        user_id=user_uuid,
                        provider_id=rjson.uuid,
                        device_id=rjson.sourceName or None,
                        recorded_at=rjson.startDate,
                        value=value,
                    ),
                )

        yield heart_rate_samples, step_samples

    def _extract_metrics_from_workout_stats(self, stats: list | None) -> EventRecordMetrics:
        heart_rate_values: list[Decimal] = []
        step_values: list[Decimal] = []

        if stats:
            for stat in stats:
                value = self._dec(stat.value)
                if value is None or stat.type is None:
                    continue
                lowered = stat.type.lower()
                if "heart" in lowered:
                    heart_rate_values.append(value)
                elif "step" in lowered:
                    step_values.append(value)

        def _compute(values: list[Decimal]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
            if not values:
                return None, None, None
            min_v = min(values)
            max_v = max(values)
            avg_v = sum(values, Decimal("0")) / Decimal(len(values))
            return min_v, max_v, avg_v

        hr_min, hr_max, hr_avg = _compute(heart_rate_values)
        steps_min, steps_max, steps_avg = _compute(step_values)
        steps_total = Decimal(sum(step_values)) if step_values else None

        return EventRecordMetrics(
            heart_rate_min=int(hr_min) if hr_min is not None else None,
            heart_rate_max=int(hr_max) if hr_max is not None else None,
            heart_rate_avg=hr_avg,
            steps_min=int(steps_min) if steps_min is not None else None,
            steps_max=int(steps_max) if steps_max is not None else None,
            steps_avg=steps_avg,
            steps_total=int(steps_total) if steps_total is not None else None,
        )

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        for record, detail in self._build_workout_bundles(raw, user_id):
            self.event_record_service.create(db_session, record)
            self.event_record_service.create_detail(db_session, detail)

        for heart_rate_records, step_records in self._build_statistic_bundles(raw, user_id):
            if heart_rate_records:
                self.time_series_service.bulk_create_samples(db_session, heart_rate_records)
            if step_records:
                self.time_series_service.bulk_create_samples(db_session, step_records)

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
