import json
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.constants.series_types.apple import (
    WorkoutStatisticType,
    get_detail_field_from_workout_statistic_type,
    get_series_type_from_sdk_metric_type,
    get_series_type_from_workout_statistic_type,
)
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
from app.utils.structured_logging import log_structured

from .device_resolution import extract_device_info
from .sleep_service import handle_sleep_data


class ImportService:
    def __init__(
        self,
        log: Logger,
    ):
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
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate, list[TimeSeriesSampleCreate]]]:
        """
        Given the parsed SyncRequest, yield tuples of
        (EventRecordCreate, EventRecordDetailCreate) ready to insert into your ORM session.
        """
        user_uuid = UUID(user_id)
        provider = request.provider

        for wjson in request.data.workouts:
            workout_id = uuid4()
            external_id = wjson.id if wjson.id else None

            device_model, software_version, original_source_name = extract_device_info(wjson.source)

            metrics, time_series_samples, duration = self._extract_metrics_from_workout_stats(
                wjson.values,
                user_uuid,
                device_model,
                software_version,
                wjson.endDate,
                provider,
                original_source_name,
            )

            if duration is None:
                duration = int((wjson.endDate - wjson.startDate).total_seconds())

            record = EventRecordCreate(
                category="workout",
                type=get_unified_apple_workout_type_sdk(wjson.type).value if wjson.type else None,
                source_name=original_source_name or "unknown",
                device_model=device_model,
                duration_seconds=int(duration),
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
                id=workout_id,
                external_id=external_id,
                source=provider,
                software_version=software_version,
                provider=provider,
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail, time_series_samples

    def _build_statistic_bundles(
        self,
        request: SyncRequest,
        user_id: str,
    ) -> list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate]:
        time_series_samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate] = []
        user_uuid = UUID(user_id)
        provider = request.provider

        for rjson in request.data.records:
            value = Decimal(str(rjson.value))

            record_type = rjson.type or ""
            series_type = get_series_type_from_sdk_metric_type(record_type)

            if not series_type:
                continue
            # Convert from meters to centimeters or ratio to percentage
            if series_type in (SeriesType.height, SeriesType.body_fat_percentage):
                value = value * 100

            # Extract device info
            device_model, software_version, original_source_name = extract_device_info(rjson.source)

            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                external_id=rjson.id,
                user_id=user_uuid,
                source=original_source_name,
                device_model=device_model,
                software_version=software_version,
                provider=provider,
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
        user_uuid: UUID,
        device_model: str | None,
        software_version: str | None,
        end_date: datetime,
        provider: str,
        source_name: str | None,
    ) -> tuple[EventRecordMetrics, list[TimeSeriesSampleCreate], int | float | None]:
        """
        Returns a tuple with the metrics, time series samples, and duration.
        """
        if stats is None:
            return EventRecordMetrics(), [], None

        stats_dict: dict[str, Decimal | int] = {}
        stats_dict["energy_burned"] = Decimal("0")
        time_series_samples: list[TimeSeriesSampleCreate] = []
        duration: float | None = None

        for stat in stats:
            value = self._dec(stat.value)
            if value is None or stat.type is None:
                continue

            # series type conversion only happens for metrics that are not in EventRecordMetrics
            series_type = get_series_type_from_workout_statistic_type(stat.type)

            if series_type:
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    external_id=None,
                    user_id=user_uuid,
                    source=source_name,
                    device_model=device_model,
                    software_version=software_version,
                    provider=provider,
                    recorded_at=end_date,
                    value=value,
                    series_type=series_type,
                )
                time_series_samples.append(sample)
                continue

            # duration is not a part of EventRecordMetrics, however it is sent as a workout statistic
            if stat.type in (WorkoutStatisticType.DURATION, WorkoutStatisticType.TOTAL_DURATION):
                duration = float(value) / 1000 if stat.unit == "ms" else float(value)
                continue

            if stat.type in (
                WorkoutStatisticType.ACTIVE_ENERGY_BURNED,
                WorkoutStatisticType.BASAL_ENERGY_BURNED,
                WorkoutStatisticType.CALORIES,
                WorkoutStatisticType.TOTAL_CALORIES,
            ):
                stats_dict["energy_burned"] += value
                continue

            detail_field = get_detail_field_from_workout_statistic_type(stat.type)
            if detail_field:
                # Apple SDK may send fractional Decimals for integer fields (e.g. stepCount)
                if detail_field in ("steps_count", "moving_time_seconds"):
                    value = int(value)
                stats_dict[detail_field] = value

        return EventRecordMetrics(**stats_dict), time_series_samples, duration

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
            records = [record for record, _, _ in workout_bundles]
            details_by_id = {detail.record_id: detail for _, detail, _ in workout_bundles}
            # Flatten all time series samples from all workouts into a single list
            time_series_samples = [sample for _, _, samples in workout_bundles for sample in samples]

            # Bulk create records - returns only IDs that were actually inserted
            inserted_ids = self.event_record_service.bulk_create(db_session, records)
            db_session.flush()

            # Filter details to only those records that were actually inserted (avoid FK violation)
            details_to_insert = [details_by_id[rid] for rid in inserted_ids if rid in details_by_id]

            # Bulk create details (requires event_record to exist due to FK)
            if details_to_insert:
                self.event_record_service.bulk_create_details(db_session, details_to_insert, detail_type="workout")
            workouts_saved = len(inserted_ids)

            # Bulk create time series samples
            if time_series_samples:
                self.timeseries_service.bulk_create_samples(db_session, time_series_samples)
                records_saved += len(time_series_samples)

        # Process time series samples (records)
        samples = self._build_statistic_bundles(request, user_id)
        if samples:
            self.timeseries_service.bulk_create_samples(db_session, samples)
            records_saved += len(samples)

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
                    action="sdk_validate_data",
                    batch_id=batch_id,
                    user_id=user_id,
                )
                return UploadDataResponse(status_code=400, response="No valid data found", user_id=user_id)

            # Extract incoming counts for logging
            provider = data.get("provider", "unknown")
            inner_data = data.get("data", {})
            incoming_records = len(inner_data.get("records", []))
            incoming_workouts = len(inner_data.get("workouts", []))
            incoming_sleep = len(inner_data.get("sleep", []))

            # Load data and get saved counts
            saved_counts = self.load_data(db_session, data, user_id=user_id, batch_id=batch_id)

            connection = self.user_connection_repo.get_by_user_and_provider(db_session, UUID(user_id), provider)
            if connection:
                self.user_connection_repo.update_last_synced_at(db_session, connection)

            # Log detailed processing results
            log_structured(
                self.log,
                "info",
                f"{provider.capitalize()} data import completed",
                provider=f"{provider}",
                action=f"{provider}_sdk_import_complete",
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
                provider=f"{provider}",
                action=f"{provider}_sdk_import_failed",
                batch_id=batch_id,
                user_id=user_id,
                error_type=type(e).__name__,
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
