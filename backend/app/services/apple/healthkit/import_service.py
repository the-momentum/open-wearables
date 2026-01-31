import json
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.constants.series_types import (
    get_series_type_from_apple_metric_type,
)
from app.constants.workout_statistics import WorkoutStatisticType
from app.constants.workout_types import get_unified_apple_workout_type_sdk
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    SeriesType,
    StepSampleCreate,
    TimeSeriesSampleCreate,
    UploadDataResponse,
)
from app.schemas.apple.healthkit.sync_request import SyncRequest, WorkoutStatistic
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

from .device_resolution import extract_device_info
from .sleep_service import handle_sleep_data


class ImportService:
    def __init__(self, log: Logger):
        self.log = log
        self.event_record_service = event_record_service
        self.timeseries_service = timeseries_service
        self.user_connection_repo = UserConnectionRepository()

    def _dec(self, value: float | int | Decimal | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def _build_workout_bundles(
        self,
        request: SyncRequest,
        user_id: str,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """
        Given the parsed SyncRequest, yield tuples of
        (EventRecordCreate, EventRecordDetailCreate) ready to insert into your ORM session.
        """
        user_uuid = UUID(user_id)
        for wjson in request.data.workouts:
            workout_id = uuid4()
            external_id = wjson.uuid if wjson.uuid else None

            metrics, duration = self._extract_metrics_from_workout_stats(wjson.workoutStatistics)

            if duration is None:
                duration = int((wjson.endDate - wjson.startDate).total_seconds())

            device_model, software_version, original_source_name = extract_device_info(wjson.source)

            record = EventRecordCreate(
                category="workout",
                type=get_unified_apple_workout_type_sdk(wjson.type).value if wjson.type else None,
                source_name="apple_health_sdk",
                device_model=device_model,
                duration_seconds=int(duration),
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
                id=workout_id,
                external_id=external_id,
                source="apple_health_sdk",
                software_version=software_version,
                provider="apple",
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail

    def _build_statistic_bundles(
        self,
        request: SyncRequest,
        user_id: str,
    ) -> list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate]:
        time_series_samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate] = []
        user_uuid = UUID(user_id)

        for rjson in request.data.records:
            value = Decimal(str(rjson.value))

            record_type = rjson.type or ""
            series_type = get_series_type_from_apple_metric_type(record_type)

            if not series_type:
                continue
            # Convert from meters to centimeters or ratio to percentage
            if series_type in (SeriesType.height, SeriesType.body_fat_percentage):
                value = value * 100

            # Extract device info
            device_model, software_version, original_source_name = extract_device_info(rjson.source)

            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                external_id=rjson.uuid,
                user_id=user_uuid,
                source="apple_health_sdk",
                device_model=device_model,
                software_version=software_version,
                provider="apple",
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
        stats: list[WorkoutStatistic] | None,
    ) -> tuple[EventRecordMetrics, int | float | None]:
        """
        Returns a dictionary with the metrics and duration.
        """
        if stats is None:
            return EventRecordMetrics(), None

        stats_dict: dict[str, Decimal | int] = {}
        stats_dict["energy_burned"] = Decimal("0")
        duration: float | None = None

        for stat in stats:
            value = self._dec(stat.value)
            if value is None or stat.type is None:
                continue

            match stat.type:
                case WorkoutStatisticType.ACTIVE_ENERGY_BURNED:
                    stats_dict["energy_burned"] += value
                case WorkoutStatisticType.AVERAGE_GROUND_CONTACT_TIME:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.AVERAGE_HEART_RATE:
                    stats_dict["heart_rate_avg"] = value
                case WorkoutStatisticType.AVERAGE_METS:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.AVERAGE_RUNNING_POWER:
                    stats_dict["average_watts"] = value
                case WorkoutStatisticType.AVERAGE_RUNNING_SPEED:
                    stats_dict["average_speed"] = value
                case WorkoutStatisticType.AVERAGE_RUNNING_STRIDE_LENGTH:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.AVERAGE_SPEED:
                    if "average_speed" not in stats_dict:
                        stats_dict["average_speed"] = value
                case WorkoutStatisticType.AVERAGE_VERTICAL_OSCILLATION:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.BASAL_ENERGY_BURNED:
                    stats_dict["energy_burned"] += value
                case WorkoutStatisticType.DISTANCE:
                    stats_dict["distance"] = value
                case WorkoutStatisticType.DURATION:
                    duration = float(value)
                case WorkoutStatisticType.ELEVATION_ASCENDED:
                    stats_dict["total_elevation_gain"] = value
                case WorkoutStatisticType.ELEVATION_DESCENDED:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.INDOOR_WORKOUT:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.LAP_LENGTH:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.MAX_HEART_RATE:
                    stats_dict["heart_rate_max"] = int(value)
                case WorkoutStatisticType.MAX_SPEED:
                    stats_dict["max_speed"] = value
                case WorkoutStatisticType.MIN_HEART_RATE:
                    stats_dict["heart_rate_min"] = int(value)
                case WorkoutStatisticType.STEP_COUNT:
                    stats_dict["steps_count"] = int(value)
                case WorkoutStatisticType.SWIMMING_LOCATION_TYPE:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.SWIMMING_STROKE_COUNT:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.WEATHER_HUMIDITY:
                    pass  # No corresponding field in EventRecordMetrics
                case WorkoutStatisticType.WEATHER_TEMPERATURE:
                    pass  # No corresponding field in EventRecordMetrics

        return EventRecordMetrics(**stats_dict), duration

    def load_data(
        self,
        db_session: DbSession,
        raw: dict,
        user_id: str,
        batch_id: str | None = None,
    ) -> dict[str, int]:
        """
        Load data into database and return counts of saved items.

        Returns:
            dict with counts: {"workouts_saved": int, "records_saved": int, "sleep_saved": int}
        """
        request = SyncRequest(**raw)
        workouts_saved = 0
        records_saved = 0
        sleep_saved = 0

        # Process workouts in batch
        workout_bundles = list(self._build_workout_bundles(request, user_id))
        if workout_bundles:
            records = [record for record, _ in workout_bundles]
            details_by_id = {detail.record_id: detail for _, detail in workout_bundles}

            # Bulk create records - returns only IDs that were actually inserted
            inserted_ids = self.event_record_service.bulk_create(db_session, records)
            db_session.flush()

            # Filter details to only those records that were actually inserted (avoid FK violation)
            details_to_insert = [details_by_id[rid] for rid in inserted_ids if rid in details_by_id]

            # Bulk create details (requires event_record to exist due to FK)
            if details_to_insert:
                self.event_record_service.bulk_create_details(db_session, details_to_insert, detail_type="workout")
            workouts_saved = len(inserted_ids)

        # Process time series samples (records)
        samples = self._build_statistic_bundles(request, user_id)
        if samples:
            self.timeseries_service.bulk_create_samples(db_session, samples)
            records_saved = len(samples)

        # Commit all workout and timeseries changes in one transaction
        db_session.commit()

        # Process sleep (count sleep segments from input)
        if request.data.sleep:
            handle_sleep_data(db_session, request, user_id)
            sleep_saved = len(request.data.sleep)

        return {
            "workouts_saved": workouts_saved,
            "records_saved": records_saved,
            "sleep_saved": sleep_saved,
        }

    def import_data_from_request(
        self,
        db_session: DbSession,
        request_content: str,
        content_type: str,
        user_id: str,
        batch_id: str | None = None,
    ) -> UploadDataResponse:
        try:
            # Parse content based on type
            if "multipart/form-data" in content_type:
                data = self._parse_multipart_content(request_content)
            else:
                data = self._parse_json_content(request_content)

            if not data:
                log_structured(
                    self.log,
                    "warning",
                    "No valid data found in request",
                    action="apple_sdk_validate_data",
                    batch_id=batch_id,
                    user_id=user_id,
                )
                return UploadDataResponse(status_code=400, response="No valid data found", user_id=user_id)

            # Extract incoming counts for logging
            inner_data = data.get("data", {})
            incoming_records = len(inner_data.get("records", []))
            incoming_workouts = len(inner_data.get("workouts", []))
            incoming_sleep = len(inner_data.get("sleep", []))

            # Load data and get saved counts
            saved_counts = self.load_data(db_session, data, user_id=user_id, batch_id=batch_id)

            connection = self.user_connection_repo.get_by_user_and_provider(db_session, UUID(user_id), "apple")
            if connection:
                self.user_connection_repo.update_last_synced_at(db_session, connection)

            # Log detailed processing results
            log_structured(
                self.log,
                "info",
                "Apple data import completed",
                action="apple_sdk_import_complete",
                batch_id=batch_id,
                user_id=user_id,
                incoming_records=incoming_records,
                incoming_workouts=incoming_workouts,
                incoming_sleep=incoming_sleep,
                records_saved=saved_counts["records_saved"],
                workouts_saved=saved_counts["workouts_saved"],
                sleep_saved=saved_counts["sleep_saved"],
            )

        except Exception as e:
            log_structured(
                self.log,
                "error",
                f"Import failed for user {user_id}: {e}",
                action="apple_sdk_import_failed",
                batch_id=batch_id,
                user_id=user_id,
                error_type=type(e).__name__,
            )
            log_and_capture_error(
                e,
                self.log,
                f"Import failed for user {user_id}: {e}",
                extra={"user_id": user_id, "batch_id": batch_id},
            )
            return UploadDataResponse(
                status_code=400,
                response=f"Import failed: {str(e)}",
                user_id=user_id,
            )

        return UploadDataResponse(status_code=200, response="Import successful", user_id=user_id)

    def _parse_multipart_content(self, content: str) -> dict | None:
        """Parse multipart form data to extract JSON."""
        # Try to find JSON start with various field patterns
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
