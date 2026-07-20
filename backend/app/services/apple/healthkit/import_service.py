import json
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.constants.series_types.sdk import (
    WorkoutStatisticType,
    get_detail_field_from_workout_statistic_type,
    get_series_type_from_metric_type,
    get_series_type_from_workout_statistic_type,
)
from app.constants.workout_types import get_unified_apple_workout_type_sdk
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import SeriesType, daily_total_flag
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.mobile_sdk import (
    SyncRequest as SDKSyncRequest,
)
from app.schemas.providers.mobile_sdk import (
    WorkoutStatistic,
)
from app.schemas.responses.upload import UploadDataResponse
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

from .device_resolution import extract_device_info
from .sleep_service import handle_sleep_data

# Health Connect's own mg/dL converter uses exactly 18.0, so values written to HC
# in mg/dL round-trip with a ~0.1% offset under this factor.
MMOL_L_TO_MG_DL = Decimal("18.0182")


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
        request: SDKSyncRequest,
        user_id: str,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate, list[TimeSeriesSampleCreate]]]:
        """
        Given the parsed SDKSyncRequest, yield tuples of
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
                wjson.zoneOffset,
                provider,
                original_source_name,
            )

            if duration is None:
                duration = int((wjson.endDate - wjson.startDate).total_seconds())

            workout_type = wjson.type.lower() if wjson.type else None
            type = get_unified_apple_workout_type_sdk(workout_type).value if workout_type else None

            record = EventRecordCreate(
                category="workout",
                type=type,
                source_name=original_source_name or "unknown",
                device_model=device_model,
                duration_seconds=int(duration),
                start_datetime=wjson.startDate,
                end_datetime=wjson.endDate,
                zone_offset=wjson.zoneOffset,
                id=workout_id,
                external_id=external_id,
                source=original_source_name,
                software_version=software_version,
                provider=provider,
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail, time_series_samples

    def _normalize_unit(self, series_type: SeriesType, value: Decimal, provider: str | None = None) -> Decimal:
        match series_type:
            # meters → cm
            case SeriesType.height | SeriesType.walking_step_length:
                return value * 100
            # 0-1 fraction → percent (body_fat only for Apple; Health Connect already reports percent)
            case SeriesType.body_fat_percentage if provider == "apple":
                return value * 100
            # HealthKit walking metrics returned as 0-1 fraction, DB stores percent
            # apple-only metrics, so no need to check if provider is apple
            case (
                SeriesType.walking_double_support_percentage
                | SeriesType.walking_asymmetry_percentage
                | SeriesType.walking_steadiness
            ):
                return value * 100
            case _:
                return value

    def _build_statistic_bundles(
        self,
        request: SDKSyncRequest,
        user_id: str,
    ) -> list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate]:
        time_series_samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate] = []
        user_uuid = UUID(user_id)
        provider = request.provider

        for rjson in request.data.records:
            value = Decimal(str(rjson.value))

            record_type = rjson.type or ""
            series_type = get_series_type_from_metric_type(record_type)

            if not series_type:
                continue
            value = self._normalize_unit(series_type, value, provider)

            # Health Connect reports blood glucose in mmol/L; the series unit is mg/dL.
            if series_type == SeriesType.blood_glucose and (rjson.unit or "").lower().startswith("mmol"):
                value = value * MMOL_L_TO_MG_DL

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
                zone_offset=rjson.zoneOffset,
                value=value,
                series_type=series_type,
                is_daily_total=daily_total_flag(series_type, is_daily=False),
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
        zone_offset: str | None,
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

            series_type = get_series_type_from_workout_statistic_type(stat.type)
            if series_type:
                time_series_samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        external_id=None,
                        user_id=user_uuid,
                        source=source_name,
                        device_model=device_model,
                        software_version=software_version,
                        provider=provider,
                        recorded_at=end_date,
                        zone_offset=zone_offset,
                        value=value,
                        series_type=series_type,
                        is_daily_total=daily_total_flag(series_type, is_daily=False),
                    )
                )
                continue

            match stat.type:
                # duration is sent as a workout statistic but stored separately
                case WorkoutStatisticType.DURATION | WorkoutStatisticType.TOTAL_DURATION:
                    duration = float(value) / 1000 if stat.unit == "ms" else float(value)
                case (
                    WorkoutStatisticType.ACTIVE_ENERGY_BURNED
                    | WorkoutStatisticType.BASAL_ENERGY_BURNED
                    | WorkoutStatisticType.CALORIES
                    | WorkoutStatisticType.TOTAL_CALORIES
                ):
                    stats_dict["energy_burned"] += value
                case _:
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
        request = SDKSyncRequest(**raw)
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
        provider = "unknown"
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

            # Extract incoming counts (best-effort; invalid types must reach validation
            # below rather than raising TypeError here)
            provider = data.get("provider", "unknown")
            inner_data = data.get("data")
            if not isinstance(inner_data, dict):
                inner_data = {}
            records = inner_data.get("records")
            workouts = inner_data.get("workouts")
            sleep = inner_data.get("sleep")
            incoming_records = len(records) if isinstance(records, list) else 0
            incoming_workouts = len(workouts) if isinstance(workouts, list) else 0
            incoming_sleep = len(sleep) if isinstance(sleep, list) else 0

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

        except ValidationError as e:
            # Payload failed schema validation; report to Sentry with the field-level errors.
            errors = e.errors()
            first = errors[0] if errors else {}
            # Drop `input` (raw record value — may contain health data/PII) and `url`
            # before sending to Sentry; keep loc/msg/type. Preserve the 20-error cap.
            safe_errors = [{k: v for k, v in err.items() if k not in ("input", "url")} for err in errors[:20]]
            log_and_capture_error(
                e,
                self.log,
                f"{provider} SDK payload failed validation for user {user_id}",
                extra={
                    "user_id": user_id,
                    "batch_id": batch_id,
                    "provider": provider,
                    "error_count": len(errors),
                    "errors": safe_errors,
                },
            )
            log_structured(
                self.log,
                "warning",
                f"{provider.capitalize()} SDK payload validation failed",
                provider=f"{provider}",
                action=f"{provider}_sdk_validation_failed",
                batch_id=batch_id,
                user_id=user_id,
                error_count=len(errors),
                first_error_loc=".".join(str(x) for x in first.get("loc", [])),
                first_error_msg=first.get("msg"),
            )
            return UploadDataResponse(
                status_code=400,
                response=f"Validation failed: {first.get('msg', 'invalid payload')}",
                user_id=user_id,
            )

        except Exception as e:
            log_and_capture_error(
                e,
                self.log,
                f"Import failed for user {user_id}",
                extra={"user_id": user_id, "batch_id": batch_id, "provider": provider},
            )
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
