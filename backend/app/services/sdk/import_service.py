import json
import time
from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable, TypedDict
from uuid import UUID, uuid4

import sentry_sdk
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.constants.entry_source import get_unified_sdk_entry_source
from app.constants.series_types.sdk import (
    WorkoutStatisticType,
    get_detail_field_from_workout_statistic_type,
    get_series_type_from_metric_type,
    get_series_type_from_workout_statistic_type,
)
from app.constants.workout_types import get_unified_sdk_workout_type
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import DeviceType, SeriesType, daily_total_flag
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    MealDetailCreate,
    StepSampleCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.providers.mobile_sdk import (
    SyncRequest as SDKSyncRequest,
)
from app.schemas.providers.mobile_sdk import (
    WorkoutStatistic,
)
from app.schemas.providers.mobile_sdk.sync_request import (
    MetricRecord,
    SleepRecord,
    SyncRequestData,
    Workout,
)
from app.schemas.responses.upload import UploadDataResponse
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.utils.exceptions import handle_exceptions
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

from .device_resolution import extract_device_info, extract_device_type
from .sleep_service import handle_sleep_data

# Health Connect's own mg/dL converter uses exactly 18.0, so values written to HC
# in mg/dL round-trip with a ~0.1% offset under this factor.
MMOL_L_TO_MG_DL = Decimal("18.0182")

# Energy series stored in kcal.
_KCAL_SERIES = frozenset({SeriesType.dietary_energy_consumed, SeriesType.dietary_energy_from_fat})

# Dietary series types plus hydration.
_MEAL_NUTRIENT_SERIES_TYPES = frozenset(
    {st for st in SeriesType if st.value.startswith("dietary_")} | {SeriesType.hydration}
)

# Correlation types: parent records that carry no measurement of their own, but group
# sibling records that reference them via their own `parentId`.
CORRELATION_LINKABLE_SERIES_TYPES: dict[str, frozenset[SeriesType]] = {
    "HKCorrelationTypeIdentifierFood": _MEAL_NUTRIENT_SERIES_TYPES,
    "FOOD": _MEAL_NUTRIENT_SERIES_TYPES,
}

_SDK_ITEM_MODELS = (("records", MetricRecord), ("sleep", SleepRecord), ("workouts", Workout))


class InvalidRecord(TypedDict):
    """A single record dropped by per-record validation (PII-free — only the location, no values)."""

    collection: str  # "records" | "sleep" | "workouts"
    index: int
    loc: str
    msg: str | None
    type: str | None


class LoadDataResult(TypedDict):
    workouts_saved: int
    meals_saved: int  # meal correlations inserted
    records_saved: int  # samples submitted
    records_inserted: int  # rows that did not exist
    records_updated: int  # rows refreshed in place
    types: list[str]  # series types written
    sleep_saved: int
    dropped: list[InvalidRecord]
    validation_ms: float


def _parse_sync_request(raw: dict) -> tuple[SDKSyncRequest, list[InvalidRecord]]:
    """Parse a raw payload into a SyncRequest, salvaging valid records when items fail.

    Fast path validates in one shot. On failure, valid records are kept and the per-item
    failures returned (PII-free: loc/msg/type). Raises ValidationError when the envelope or
    a container shape is invalid — nothing salvageable, so the batch is rejected (400).
    """
    try:
        return SDKSyncRequest(**raw), []
    except ValidationError:
        pass  # fall through to per-item validation

    # Only individual records are salvageable. A malformed container shape (data not a dict,
    # or a collection not a list) is not — re-validate to re-raise the real ValidationError.
    data = raw.get("data")
    if not isinstance(data, dict) or any(not isinstance(data.get(key, []), list) for key, _ in _SDK_ITEM_MODELS):
        return SDKSyncRequest(**raw), []

    kept: dict[str, list] = {}
    dropped: list[InvalidRecord] = []
    for key, model in _SDK_ITEM_MODELS:
        good: list = []
        for idx, item in enumerate(data.get(key, [])):
            try:
                good.append(model.model_validate(item))
            except ValidationError as exc:
                err = (exc.errors() or [{}])[0]
                dropped.append(
                    {
                        "collection": key,
                        "index": idx,
                        "loc": ".".join(str(x) for x in err.get("loc", [])),
                        "msg": err.get("msg"),
                        "type": err.get("type"),
                    }
                )
        kept[key] = good

    # Reconstruct via model_validate so Pydantic still rejects a bad envelope; `data` now
    # carries only the kept records.
    request = SDKSyncRequest.model_validate(
        {**raw, "data": SyncRequestData(records=kept["records"], sleep=kept["sleep"], workouts=kept["workouts"])}
    )
    return request, dropped


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
        """Convert a raw numeric value to `Decimal`, passing `None` through unchanged."""
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
            device_type = extract_device_type(wjson.source)

            metrics, time_series_samples, duration = self._extract_metrics_from_workout_stats(
                wjson.values,
                user_uuid,
                device_model,
                software_version,
                wjson.endDate,
                wjson.zoneOffset,
                provider,
                original_source_name,
                device_type,
            )

            if duration is None:
                duration = int((wjson.endDate - wjson.startDate).total_seconds())

            workout_type = wjson.type.lower() if wjson.type else None
            type = get_unified_sdk_workout_type(workout_type).value if workout_type else None

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
                device_type=device_type,
                provider=provider,
                user_id=user_uuid,
            )

            entry_source = get_unified_sdk_entry_source(wjson.source.recording_method if wjson.source else None)
            if entry_source is not None:
                metrics["entry_source"] = entry_source

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail, time_series_samples

    def _build_meal_bundles(
        self,
        correlation_records: list[MetricRecord],
        provider: str,
        user_id: str,
    ) -> Generator[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """Build meal (EventRecordCreate, MealDetailCreate) pairs from HealthKit
        correlation records (e.g. HKCorrelationTypeIdentifierFood).

        `correlation_records` are the `records[]` entries already classified as meal
        correlations by `load_data` - a correlation record has no measurement value of its
        own; its sibling records reference it via their own `parentId`, resolved separately
        in `_build_statistic_bundles`.
        """
        user_uuid = UUID(user_id)

        for rjson in correlation_records:
            if not rjson.id:
                continue

            meal_id = uuid4()
            metadata = rjson.metadata if isinstance(rjson.metadata, dict) else {}
            device_model, software_version, original_source_name = extract_device_info(rjson.source)

            record = EventRecordCreate(
                category="meal",
                type=rjson.type,
                source_name=original_source_name or "unknown",
                device_model=device_model,
                start_datetime=rjson.startDate,
                end_datetime=rjson.endDate,
                zone_offset=rjson.zoneOffset,
                id=meal_id,
                external_id=rjson.id,
                source=original_source_name,
                software_version=software_version,
                provider=provider,
                user_id=user_uuid,
            )
            detail = MealDetailCreate(
                record_id=meal_id,
                title=metadata.get("title"),
                meal_type=metadata.get("mealType"),
            )

            yield record, detail

    @staticmethod
    def _nutrients_by_meal(
        samples: Iterable[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate],
        meal_ids: set[UUID],
    ) -> dict[UUID, dict[SeriesType, Decimal]]:
        """Group this batch's nutrient samples by their linked meal, for the meal.created webhook.

        Samples are matched via `event_record_id` (set in _build_statistic_bundles from
        correlation_id_map), the same link `_nutrients_by_meal` on EventRecordService reads
        back from the database for the Google Health path.
        """
        result: dict[UUID, dict[SeriesType, Decimal]] = {}
        for sample in samples:
            if sample.event_record_id is None or sample.event_record_id not in meal_ids:
                continue
            value = sample.value if isinstance(sample.value, Decimal) else Decimal(str(sample.value))
            bucket = result.setdefault(sample.event_record_id, {})
            bucket[sample.series_type] = bucket.get(sample.series_type, Decimal("0")) + value
        return result

    def _normalize_unit(self, series_type: SeriesType, value: Decimal, provider: str | None = None) -> Decimal:
        """Rescale a value into the series' stored unit for series where the SDK unit varies by provider."""
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

    @handle_exceptions
    def _build_statistic_bundles(
        self,
        records: list[MetricRecord],
        provider: str,
        user_id: str,
        correlation_id_map: dict[str, UUID] | None = None,
        correlation_type_by_external_id: dict[str, str] | None = None,
    ) -> list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate]:
        """Build time series samples from `records[]` (correlation records themselves
        already excluded by `load_data` - see `_build_meal_bundles`).

        `correlation_id_map` links a sample to its parent (via `parentId`) when that
        correlation was already resolved earlier in the same batch. `correlation_type_by_
        external_id` says which correlation type that parent is, so the link is only made
        when the sample's own series type is one CORRELATION_LINKABLE_SERIES_TYPES allows
        for that specific correlation type - a heart rate reading whose parentId happens to
        match a meal's external_id, say, must stay a loose sample. No match, or no
        `parentId`, is also a loose sample.
        """
        time_series_samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate] = []
        user_uuid = UUID(user_id)
        correlation_id_map = correlation_id_map or {}
        correlation_type_by_external_id = correlation_type_by_external_id or {}

        for rjson in records:
            record_type = rjson.type or ""
            value = Decimal(str(rjson.value))
            unit = (rjson.unit or "").strip().lower()

            series_type = get_series_type_from_metric_type(record_type)

            if not series_type:
                continue
            value = self._normalize_unit(series_type, value, provider)

            # Health Connect reports blood glucose in mmol/L; the series unit is mg/dL.
            if series_type == SeriesType.blood_glucose and unit.startswith("mmol"):
                value = value * MMOL_L_TO_MG_DL

            # Convert hydration units to mL
            if series_type == SeriesType.hydration and unit in ("l", "liter", "liters", "litre", "litres"):
                value *= 1000

            # Energy is stored in kcal. Case matters: "cal" is a small calorie (1/1000 kcal),
            # "Cal" is the food Calorie (= kcal).
            if series_type in _KCAL_SERIES and (rjson.unit or "").strip() == "cal":
                value = value / 1000

            # Extract device info
            device_model, software_version, original_source_name = extract_device_info(rjson.source)

            # Links this sample to its parent correlation, when it has one, its own type is
            # allowed for THAT correlation's type, and the correlation was resolved in this
            # same batch. None for a loose sample.
            parent_type = correlation_type_by_external_id.get(rjson.parentId) if rjson.parentId else None
            linkable_types = CORRELATION_LINKABLE_SERIES_TYPES.get(parent_type, frozenset())
            event_record_id = correlation_id_map.get(rjson.parentId) if series_type in linkable_types else None

            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                external_id=rjson.id,
                user_id=user_uuid,
                source=original_source_name,
                device_model=device_model,
                software_version=software_version,
                device_type=extract_device_type(rjson.source),
                provider=provider,
                recorded_at=rjson.startDate,
                zone_offset=rjson.zoneOffset,
                value=value,
                series_type=series_type,
                is_daily_total=daily_total_flag(series_type, is_daily=False),
                event_record_id=event_record_id,
            )

            match series_type:
                case SeriesType.heart_rate:
                    time_series_samples.append(HeartRateSampleCreate(**sample.model_dump()))
                case SeriesType.steps:
                    time_series_samples.append(StepSampleCreate(**sample.model_dump()))
                case _:
                    time_series_samples.append(sample)

        return time_series_samples

    def _prune_stale_meal_samples(
        self,
        db_session: DbSession,
        samples: list[HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate],
        meal_ids: set[UUID],
    ) -> None:
        """Delete a meal's previously-stored samples whose type this batch no longer reports.

        A meal only reports the nutrient types it currently has; an item removed from it
        (e.g. the user deletes a food from the entry) simply won't be in this set, so this
        deletes whatever this batch no longer reports for that meal - otherwise a removed
        item's sample would never get cleaned up. A meal absent from `samples` entirely
        (this batch says nothing about its nutrients) is left untouched.

        `meal_ids` are the ids this same call just upserted as meals - `sample.event_record_id`
        is trusted only against that set, not merely "is not None", so a future bug that sets
        event_record_id on a sample for some other purpose can't get its rows silently swept
        into meal reconciliation.
        """
        meal_sample_types: dict[UUID, set[SeriesType]] = {}
        for sample in samples:
            if sample.event_record_id is None or sample.event_record_id not in meal_ids:
                continue
            meal_sample_types.setdefault(sample.event_record_id, set()).add(sample.series_type)
        for meal_id, types in meal_sample_types.items():
            self.event_record_service.data_point_series_repo.delete_stale_for_event_record(db_session, meal_id, types)

    def _compute_aggregates(self, values: list[Decimal]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """Return (min, max, avg) for `values`, or `(None, None, None)` when empty."""
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
        device_type: DeviceType | None = None,
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
                        device_type=device_type,
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
    ) -> LoadDataResult:
        """
        Load data into database and return counts of saved items plus per-record failures.
        """
        # Per-record validation: keep valid records, drop+report the invalid ones instead
        # of failing the whole batch. Raises ValidationError only if the envelope is invalid.
        # validation_ms measures the parse/per-record pass so we can watch the cost of a
        # malformed payload in the logs.
        started = time.perf_counter()
        request, dropped = _parse_sync_request(raw)
        validation_ms = round((time.perf_counter() - started) * 1000, 1)
        workouts_saved = 0
        meals_saved = 0
        records_saved = 0
        records_inserted = 0
        records_updated = 0
        sleep_saved = 0
        types: set[str] = set()

        # Split records[] once into correlations (meal, and whatever future correlation
        # types CORRELATION_LINKABLE_SERIES_TYPES grows) vs everything else, instead of each
        # builder re-scanning the full list and skipping what the other one handles.
        # correlation_type_by_external_id lets _build_statistic_bundles check a child's own
        # type against the SPECIFIC correlation it's linking to, not just "some correlation".
        correlation_records: list[MetricRecord] = []
        records: list[MetricRecord] = []
        correlation_type_by_external_id: dict[str, str] = {}
        for rjson in request.data.records:
            record_type = rjson.type or ""
            if record_type in CORRELATION_LINKABLE_SERIES_TYPES:
                correlation_records.append(rjson)
                if rjson.id:
                    correlation_type_by_external_id[rjson.id] = record_type
            else:
                records.append(rjson)

        # Process meal correlations first, so
        # their internal ids exist before nutrient samples try to link to them.
        meal_bundles = list(self._build_meal_bundles(correlation_records, request.provider, user_id))
        correlation_id_map: dict[str, UUID] = {}
        meal_ids: set[UUID] = set()
        # Meals newly inserted this batch, kept around (record + detail) so meal.created can
        # be scheduled once their nutrient samples are known below - see _nutrients_by_meal.
        newly_inserted_meals: dict[UUID, tuple[EventRecordCreate, EventRecordDetailCreate]] = {}
        for record, detail in meal_bundles:
            try:
                saved, inserted = self.event_record_service.create_or_update_meal(db_session, record, detail)
            except IntegrityError:
                log_structured(
                    self.log,
                    "warning",
                    "SDK meal correlation could not be reconciled - skipping",
                    action="sdk_meal_conflict_skipped",
                    batch_id=batch_id,
                    user_id=user_id,
                    provider=request.provider,
                    external_id=record.external_id,
                    start_datetime=record.start_datetime.isoformat(),
                    end_datetime=record.end_datetime.isoformat(),
                )
                continue
            if inserted:
                meals_saved += 1
                newly_inserted_meals[saved.id] = (record, detail)
            meal_ids.add(saved.id)
            if record.external_id:
                correlation_id_map[record.external_id] = saved.id

        # Process workouts in batch
        workout_bundles = list(self._build_workout_bundles(request, user_id))
        if workout_bundles:
            workout_records = [record for record, _, _ in workout_bundles]
            details_by_id = {detail.record_id: detail for _, detail, _ in workout_bundles}
            # Flatten all time series samples from all workouts into a single list
            time_series_samples = [sample for _, _, samples in workout_bundles for sample in samples]

            # Bulk create records - returns only IDs that were actually inserted
            inserted_ids = self.event_record_service.bulk_create(db_session, workout_records)
            db_session.flush()

            # Filter details to only those records that were actually inserted (avoid FK violation)
            details_to_insert = [details_by_id[rid] for rid in inserted_ids if rid in details_by_id]

            # Bulk create details (requires event_record to exist due to FK)
            if details_to_insert:
                self.event_record_service.bulk_create_details(db_session, details_to_insert, detail_type="workout")
            workouts_saved = len(inserted_ids)

            # Bulk create time series samples
            if time_series_samples:
                counts = self.timeseries_service.bulk_create_samples(db_session, time_series_samples)
                records_saved += len(time_series_samples)
                records_inserted += counts.inserted
                records_updated += counts.updated
                types.update(sample.series_type.value for sample in time_series_samples)

        # Process time series samples (records)
        samples = self._build_statistic_bundles(
            records, request.provider, user_id, correlation_id_map, correlation_type_by_external_id
        )
        if samples:
            self._prune_stale_meal_samples(db_session, samples, meal_ids)

            counts = self.timeseries_service.bulk_create_samples(db_session, samples)
            records_saved += len(samples)
            records_inserted += counts.inserted
            records_updated += counts.updated
            types.update(sample.series_type.value for sample in samples)

        # Schedule meal.created for newly inserted meals now that the nutrient samples built
        # above are known - create_or_update_meal itself doesn't fire it (see its docstring).
        if newly_inserted_meals:
            meal_nutrients = self._nutrients_by_meal(samples, set(newly_inserted_meals.keys()))
            for meal_id, (meal_record, meal_detail) in newly_inserted_meals.items():
                self.event_record_service.schedule_meal_webhook(
                    db_session, meal_id, meal_record, meal_detail, meal_nutrients.get(meal_id)
                )

        # Commit all workout and timeseries changes in one transaction
        db_session.commit()

        # Process sleep (count sleep segments from input)
        if request.data.sleep:
            handle_sleep_data(db_session, request, user_id)
            sleep_saved = len(request.data.sleep)

        return {
            "workouts_saved": workouts_saved,
            "meals_saved": meals_saved,
            "records_saved": records_saved,
            "records_inserted": records_inserted,
            "records_updated": records_updated,
            "types": sorted(types),
            "sleep_saved": sleep_saved,
            "dropped": dropped,
            "validation_ms": validation_ms,
        }

    def import_data_from_request(
        self,
        db_session: DbSession,
        request_content: str,
        content_type: str,
        user_id: str,
        batch_id: str | None = None,
    ) -> UploadDataResponse:
        """Parse, validate, and load an SDK sync request, returning a best-effort response.

        Always returns a 200/400 `UploadDataResponse` rather than raising - validation and
        processing failures are caught, logged, reported to Sentry, and turned into a response
        instead of propagating to the caller.
        """
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
                records_inserted=saved_counts["records_inserted"],
                records_updated=saved_counts["records_updated"],
                workouts_saved=saved_counts["workouts_saved"],
                sleep_saved=saved_counts["sleep_saved"],
                validation_ms=saved_counts["validation_ms"],
            )

            dropped = saved_counts.get("dropped") or []
            if dropped:
                # Partial success: some records failed per-record validation. The good
                # ones are already saved above; report the exact field errors to Sentry
                # (PII-free: loc/msg/type) so we keep full visibility into what was lost.
                with sentry_sdk.push_scope() as scope:
                    scope.set_level("warning")
                    scope.set_context(
                        "dropped_records",
                        {
                            "batch_id": batch_id,
                            "user_id": user_id,
                            "provider": provider,
                            "dropped_count": len(dropped),
                            "errors": dropped[:20],
                        },
                    )
                    sentry_sdk.capture_message(f"{provider} SDK payload: dropped invalid records, kept the rest")
                # Compose the full location (collection[index].field) so the log one-liner
                # says which record failed, not just the field — the per-record `loc` is
                # relative to a single record. The full breakdown is in the Sentry context.
                first = dropped[0]
                first_loc = f"{first['collection']}[{first['index']}]"
                if first.get("loc"):
                    first_loc += f".{first['loc']}"
                log_structured(
                    self.log,
                    "warning",
                    f"{provider.capitalize()} SDK dropped invalid records",
                    provider=f"{provider}",
                    action=f"{provider}_sdk_records_dropped",
                    batch_id=batch_id,
                    user_id=user_id,
                    dropped_count=len(dropped),
                    first_error_loc=first_loc,
                    first_error_msg=first["msg"],
                )

            return UploadDataResponse(
                status_code=200,
                response="Import successful",
                user_id=user_id,
                dropped_count=len(dropped),
                records_saved=saved_counts["records_saved"],
                records_inserted=saved_counts["records_inserted"],
                records_updated=saved_counts["records_updated"],
                types=saved_counts["types"],
                workouts_saved=saved_counts["workouts_saved"],
                meals_saved=saved_counts["meals_saved"],
                sleep_saved=saved_counts["sleep_saved"],
            )

        except ValidationError as e:
            # Reached ONLY when the envelope itself is invalid (provider/sdkVersion/
            # syncTimestamp/data shape) — _parse_sync_request re-raised because nothing was
            # salvageable. Per-record failures never reach here: they are collected inside
            # load_data and handled above as a partial success. Report + 400 the whole batch.
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
