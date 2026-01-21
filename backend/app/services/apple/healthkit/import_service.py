import json
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.constants.series_types import (
    get_series_type_from_apple_metric_type,
)
from app.constants.workout_types import get_unified_apple_workout_type_sdk
from app.database import DbSession
from app.repositories.device_repository import DeviceRepository
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    HKRecordJSON,
    HKWorkoutJSON,
    HKWorkoutStatisticJSON,
    RootJSON,
    SeriesType,
    StepSampleCreate,
    TimeSeriesSampleCreate,
    UploadDataResponse,
)
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error

from .device_resolution import resolve_device
from .sleep_service import handle_sleep_data


class ImportService:
    def __init__(self, log: Logger):
        self.log = log
        self.event_record_service = event_record_service
        self.timeseries_service = timeseries_service
        self.device_repo = DeviceRepository()

    def _dec(self, value: float | int | Decimal | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def _build_workout_bundles(
        self,
        db: DbSession,
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
            external_id = wjson.uuid if wjson.uuid else None

            metrics, duration = self._extract_metrics_from_workout_stats(wjson.workoutStatistics)

            if duration is None:
                duration = int((wjson.endDate - wjson.startDate).total_seconds())

            # Resolve device mapping
            device_id = resolve_device(db, self.device_repo, wjson.source, wjson.sourceName)

            record = EventRecordCreate(
                category="workout",
                type=get_unified_apple_workout_type_sdk(wjson.type).value if wjson.type else None,
                source_name=wjson.sourceName or "Apple Health",
                device_id=device_id,
                duration_seconds=int(duration),
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
                id=workout_id,
                external_id=external_id,
                provider_name="Apple",
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail

    def _build_statistic_bundles(
        self,
        db: DbSession,
        raw: dict,
        user_id: str,
    ) -> list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate]:
        root = RootJSON(**raw)
        records_raw = root.data.get("records", [])
        time_series_samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate] = []
        user_uuid = UUID(user_id)

        for r in records_raw:
            rjson = HKRecordJSON(**r)
            value = Decimal(str(rjson.value))

            record_type = rjson.type or ""
            series_type = get_series_type_from_apple_metric_type(record_type)
            if not series_type:
                continue
            # Convert from meters to centimeters or ratio to percentage
            if series_type in (SeriesType.height, SeriesType.body_fat_percentage):
                value = value * 100

            # Resolve device mapping
            device_id = resolve_device(db, self.device_repo, rjson.source, rjson.sourceName)

            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                external_id=rjson.uuid,
                user_id=user_uuid,
                provider_name="Apple",
                device_id=device_id,
                recorded_at=rjson.startDate,
                value=value,
                series_type=series_type,
            )

            match series_type:
                case SeriesType.heart_rate:
                    time_series_samples.append(HeartRateSampleCreate(**sample.model_dump()))
                case SeriesType.steps:
                    time_series_samples.append(StepSampleCreate(**sample.model_dump()))
                case _:
                    time_series_samples.append(sample)

        return time_series_samples

    def _compute_aggregates(self, values: list[Decimal]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        if not values:
            return None, None, None
        min_v = min(values)
        max_v = max(values)
        avg_v = sum(values, Decimal("0")) / Decimal(len(values))
        return min_v, max_v, avg_v

    def _extract_metrics_from_workout_stats(
        self,
        stats: list[HKWorkoutStatisticJSON] | None,
    ) -> tuple[EventRecordMetrics, int | float | None]:
        """
        Returns a dictionary with the metrics and duration.
        """
        if stats is None:
            return EventRecordMetrics(), None

        stats_dict: dict[str, Decimal] = {}
        stats_dict["energy_burned"] = Decimal("0")
        duration: float | None = None

        for stat in stats:
            value = self._dec(stat.value)
            if value is None or stat.type is None:
                continue

            match stat.type:
                case "activeEnergyBurned":
                    stats_dict["energy_burned"] += value
                case "averageGroundContactTime":
                    pass  # No corresponding field in EventRecordMetrics
                case "averageHeartRate":
                    stats_dict["heart_rate_avg"] = value
                case "averageMETs":
                    pass  # No corresponding field in EventRecordMetrics
                case "averageRunningPower":
                    stats_dict["average_watts"] = value
                case "averageRunningSpeed":
                    stats_dict["average_speed"] = value
                case "averageRunningStrideLength":
                    pass  # No corresponding field in EventRecordMetrics
                case "averageSpeed":
                    if "average_speed" not in stats_dict:
                        stats_dict["average_speed"] = value
                case "averageVerticalOscillation":
                    pass  # No corresponding field in EventRecordMetrics
                case "basalEnergyBurned":
                    stats_dict["energy_burned"] += value
                case "distance":
                    stats_dict["distance"] = value
                case "duration":
                    duration = float(value)
                case "elevationAscended":
                    stats_dict["total_elevation_gain"] = value
                case "elevationDescended":
                    pass  # No corresponding field in EventRecordMetrics
                case "indoorWorkout":
                    pass  # No corresponding field in EventRecordMetrics
                case "lapLength":
                    pass  # No corresponding field in EventRecordMetrics
                case "maxHeartRate":
                    stats_dict["heart_rate_max"] = value
                case "maxSpeed":
                    stats_dict["max_speed"] = value
                case "minHeartRate":
                    stats_dict["heart_rate_min"] = value
                case "stepCount":
                    stats_dict["steps_count"] = value
                case "swimmingLocationType":
                    pass  # No corresponding field in EventRecordMetrics
                case "swimmingStrokeCount":
                    pass  # No corresponding field in EventRecordMetrics
                case "weatherHumidity":
                    pass  # No corresponding field in EventRecordMetrics
                case "weatherTemperature":
                    pass  # No corresponding field in EventRecordMetrics
                case _:
                    continue

        return EventRecordMetrics(**stats_dict), duration

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        for record, detail in self._build_workout_bundles(db_session, raw, user_id):
            created_or_existing_record = self.event_record_service.create(db_session, record)
            # Always use the returned record's ID (whether newly created or existing)
            detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
            self.event_record_service.create_detail(db_session, detail_for_record)

        samples = self._build_statistic_bundles(db_session, raw, user_id)
        self.timeseries_service.bulk_create_samples(db_session, samples)

        handle_sleep_data(db_session, raw, user_id)

        return True

    def import_data_from_request(
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
                return UploadDataResponse(status_code=400, response="No valid data found", user_id=user_id)

            # Load data using provided database session
            self.load_data(db_session, data, user_id=user_id)

        except Exception as e:
            log_and_capture_error(e, self.log, f"Import failed for user {user_id}: {e}", extra={"user_id": user_id})
            return UploadDataResponse(status_code=400, response=f"Import failed: {str(e)}", user_id=user_id)

        return UploadDataResponse(status_code=200, response="Import successful", user_id=user_id)

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
