from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import (
    DataPointSeries,
    DataSource,
    EventRecord,
    EventRecordDetail,
    SleepDetails,
    WorkoutDetails,
)
from app.repositories import (
    DataPointSeriesRepository,
    DataSourceRepository,
    EventRecordDetailRepository,
    EventRecordRepository,
)
from app.schemas.enums import WORKOUTS_WITH_PACE
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordQueryParams,
    EventRecordResponse,
    EventRecordUpdate,
)
from app.schemas.model_crud.activities.sleep import SleepStage
from app.schemas.responses.activity import SleepSession, SleepStagesSummary, Workout, WorkoutDetailed
from app.schemas.utils import (
    PaginatedResponse,
    Pagination,
    TimeseriesMetadata,
)
from app.schemas.utils import (
    SourceMetadata as DataSourceSchema,
)
from app.services.outgoing_webhooks.events import on_sleep_created, on_workout_created
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor


class EventRecordService(
    AppService[EventRecordRepository, EventRecord, EventRecordCreate, EventRecordUpdate],
):
    """Service coordinating CRUD access for unified health records."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(crud_model=EventRecordRepository, model=EventRecord, log=log, **kwargs)
        self.event_record_detail_repo = EventRecordDetailRepository(EventRecordDetail)
        self.data_source_repo = DataSourceRepository()
        self.data_point_series_repo = DataPointSeriesRepository(DataPointSeries)

    def _resolve_avg_hr(
        self,
        db_session: DbSession,
        records: list[EventRecord],
    ) -> dict[UUID, int | None]:
        """Return avg HR for each workout record.

        Uses stored heart_rate_avg where available, falls back to a single batch query
        against data_point_series for records that don't have it.
        """
        result: dict[UUID, int | None] = {}
        missing = []

        for r in records:
            details = r.detail if isinstance(r.detail, WorkoutDetails) else None
            if details and details.heart_rate_avg is not None:
                result[r.id] = round(details.heart_rate_avg)
            else:
                result[r.id] = None
                missing.append((r.id, r.data_source_id, r.start_datetime, r.end_datetime))

        if missing:
            computed = self.data_point_series_repo.get_avg_hr_for_workout_batch(db_session, missing)
            result.update(computed)

        return result

    def _build_response(
        self,
        record: EventRecord,
        data_source: DataSource,
    ) -> EventRecordResponse:
        return EventRecordResponse(
            id=record.id,
            external_id=record.external_id,
            category=record.category,
            type=record.type,
            source_name=record.source_name,
            duration_seconds=record.duration_seconds,
            start_datetime=record.start_datetime,
            end_datetime=record.end_datetime,
            zone_offset=record.zone_offset,
            data_source_id=record.data_source_id,
            user_id=data_source.user_id,
            source=data_source.source,
        )

    def create_detail(
        self,
        db_session: DbSession,
        detail: EventRecordDetailCreate,
        detail_type: str = "workout",
    ) -> EventRecordDetail:
        result = self.event_record_detail_repo.create(db_session, detail, detail_type=detail_type)  # type: ignore[return-value]
        record = db_session.get(EventRecord, detail.record_id)
        if record is not None and record.data_source_id is not None:
            data_source = db_session.get(DataSource, record.data_source_id)
            if data_source is not None:
                self._emit_event_record_webhook(record, data_source, detail)
        return result  # type: ignore[return-value]

    def find_adjacent_sleep_record(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        threshold_minutes: int,
        source: str | None = None,
        provider: str | None = None,
    ) -> EventRecord | None:
        """Find an existing sleep session adjacent to [start_time, end_time]."""
        return self.crud.find_adjacent_sleep_record(
            db_session, user_id, start_time, end_time, threshold_minutes, source=source, provider=provider
        )

    def create_or_merge_sleep(
        self,
        db_session: DbSession,
        user_id: UUID,
        record: EventRecordCreate,
        detail: EventRecordDetailCreate,
        threshold_minutes: int,
    ) -> EventRecord:
        """Create a sleep record, merging with any adjacent session within threshold_minutes.

        When an adjacent session already exists in the database within the gap threshold,
        the two records are merged: the time window expands to cover both, stage minutes
        are summed (or recomputed from the merged stage timeline when windows overlap and
        stages are available), and efficiency is recalculated as a time-in-bed-weighted
        average over sessions that have a non-None score.  The merged record is created
        first, and the old record is deleted only after a successful insert — so a failure
        never loses the original data.
        """
        result, inserted, final_detail = self._create_or_merge_sleep_inner(
            db_session, user_id, record, detail, threshold_minutes
        )
        if inserted:
            eff = final_detail.sleep_efficiency_score
            has_stages = any(
                [
                    final_detail.sleep_awake_minutes,
                    final_detail.sleep_light_minutes,
                    final_detail.sleep_deep_minutes,
                    final_detail.sleep_rem_minutes,
                ]
            )
            on_sleep_created(
                record_id=result.id,
                user_id=user_id,
                provider=record.provider or record.source_name,
                device=record.device_model,
                start_time=result.start_datetime.isoformat(),
                end_time=result.end_datetime.isoformat(),
                zone_offset=record.zone_offset,
                duration_seconds=result.duration_seconds,
                efficiency_percent=float(eff) if eff is not None else None,
                stages={
                    "awake_minutes": final_detail.sleep_awake_minutes,
                    "light_minutes": final_detail.sleep_light_minutes,
                    "deep_minutes": final_detail.sleep_deep_minutes,
                    "rem_minutes": final_detail.sleep_rem_minutes,
                }
                if has_stages
                else None,
                is_nap=final_detail.is_nap,
            )
        return result

    def _create_or_merge_sleep_inner(
        self,
        db_session: DbSession,
        user_id: UUID,
        record: EventRecordCreate,
        detail: EventRecordDetailCreate,
        threshold_minutes: int,
    ) -> tuple[EventRecord, bool, EventRecordDetailCreate]:
        adjacent = self.find_adjacent_sleep_record(
            db_session,
            user_id,
            record.start_datetime,
            record.end_datetime,
            threshold_minutes,
            source=record.source,
            provider=record.provider,
        )

        if adjacent is not None:
            # Same external_id → re-ingestion of the same session (e.g. webhook
            # retry, score update).  Replace the detail with fresh values instead
            # of accumulating them on top of the existing ones.
            if record.external_id is not None and adjacent.external_id == record.external_id:
                for field in ("start_datetime", "end_datetime", "zone_offset"):
                    new_val = getattr(record, field, None)
                    if new_val is not None:
                        setattr(adjacent, field, new_val)
                adjacent.duration_seconds = int((adjacent.end_datetime - adjacent.start_datetime).total_seconds())
                db_session.flush()
                self.event_record_detail_repo.delete_by_record_id(db_session, adjacent.id)
                self.event_record_detail_repo.create_and_flush(
                    db_session,
                    detail.model_copy(update={"record_id": adjacent.id}),
                    detail_type="sleep",
                )
                db_session.commit()
                return adjacent, False, detail

            adj_detail: SleepDetails | None = adjacent.detail if isinstance(adjacent.detail, SleepDetails) else None

            def _adj_int(attr: str) -> int:
                return (getattr(adj_detail, attr) or 0) if adj_detail else 0

            adj_in_bed = _adj_int("sleep_time_in_bed_minutes")
            new_in_bed = detail.sleep_time_in_bed_minutes or 0
            merged_in_bed = adj_in_bed + new_in_bed

            # Weighted efficiency: only include sessions that have a non-None score
            # so a missing score on one session does not dilute the merged average.
            merged_efficiency: Decimal | None = None
            eff_numerator = 0.0
            eff_denominator = 0
            if adj_detail and adj_detail.sleep_efficiency_score and adj_in_bed > 0:
                eff_numerator += float(adj_detail.sleep_efficiency_score) * adj_in_bed
                eff_denominator += adj_in_bed
            if detail.sleep_efficiency_score and new_in_bed > 0:
                eff_numerator += float(detail.sleep_efficiency_score) * new_in_bed
                eff_denominator += new_in_bed
            if eff_denominator > 0:
                merged_efficiency = Decimal(str(round(eff_numerator / eff_denominator, 2)))

            # Merge sleep_stages: convert DB dicts back to SleepStage, concatenate, sort
            adj_stages_raw = (adj_detail.sleep_stages if adj_detail else None) or []
            adj_stages = [SleepStage.model_validate(s) for s in adj_stages_raw]
            new_stages = list(detail.sleep_stages or [])
            merged_stages: list[SleepStage] | None = None
            if adj_stages or new_stages:
                merged_stages = sorted(adj_stages + new_stages, key=lambda s: s.start_time)

            merged_start = min(adjacent.start_datetime, record.start_datetime)
            merged_end = max(adjacent.end_datetime, record.end_datetime)

            # Compute per-stage minute totals.  When the windows actually overlap
            # and stage intervals are available, recompute from the merged timeline
            # (clipping overlaps — consistent with Apple SDK's _calculate_final_metrics)
            # to avoid double-counting the overlapping period.  For non-overlapping
            # sessions simple summation is exact.
            overlap_seconds = max(
                0,
                (
                    min(adjacent.end_datetime, record.end_datetime)
                    - max(adjacent.start_datetime, record.start_datetime)
                ).total_seconds(),
            )
            if overlap_seconds > 0 and merged_stages:
                deep_secs = light_secs = rem_secs = awake_secs = sleeping_secs = 0.0
                last_end = None
                for s in merged_stages:  # already sorted above
                    s_start, s_end = s.start_time, s.end_time
                    if last_end is not None and s_start < last_end:
                        s_start = last_end
                    if s_start >= s_end:
                        continue
                    dur = (s_end - s_start).total_seconds()
                    stage_str = str(s.stage)
                    if stage_str == "deep":
                        deep_secs += dur
                    elif stage_str == "light":
                        light_secs += dur
                    elif stage_str == "rem":
                        rem_secs += dur
                    elif stage_str == "awake":
                        awake_secs += dur
                    elif stage_str == "sleeping":
                        sleeping_secs += dur
                    last_end = s_end
                merged_deep = int(deep_secs / 60)
                merged_light = int(light_secs / 60)
                merged_rem = int(rem_secs / 60)
                merged_awake = int(awake_secs / 60)
                merged_total = merged_deep + merged_light + merged_rem + int(sleeping_secs / 60)
            else:
                merged_deep = _adj_int("sleep_deep_minutes") + (detail.sleep_deep_minutes or 0)
                merged_light = _adj_int("sleep_light_minutes") + (detail.sleep_light_minutes or 0)
                merged_rem = _adj_int("sleep_rem_minutes") + (detail.sleep_rem_minutes or 0)
                merged_awake = _adj_int("sleep_awake_minutes") + (detail.sleep_awake_minutes or 0)
                merged_total = _adj_int("sleep_total_duration_minutes") + (detail.sleep_total_duration_minutes or 0)

            self.logger.info(
                "Merging adjacent sleep records: %s (%s – %s) + %s (%s – %s)",
                adjacent.id,
                adjacent.start_datetime,
                adjacent.end_datetime,
                record.id,
                record.start_datetime,
                record.end_datetime,
            )

            merged_detail_fields = {
                "sleep_deep_minutes": merged_deep,
                "sleep_light_minutes": merged_light,
                "sleep_rem_minutes": merged_rem,
                "sleep_awake_minutes": merged_awake,
                "sleep_total_duration_minutes": merged_total,
                "sleep_time_in_bed_minutes": merged_in_bed,
                "sleep_efficiency_score": merged_efficiency,
                "is_nap": bool(adj_detail.is_nap if adj_detail else False) and bool(detail.is_nap or False),
                "sleep_stages": merged_stages,
            }

            # When the merged window is identical to the existing record's window
            # (new session fully contained within adjacent), inserting a new record
            # would violate the unique constraint on (data_source_id, start, end).
            # Detect this upfront and update the detail in-place instead.
            same_window = (
                merged_start == adjacent.start_datetime
                and merged_end == adjacent.end_datetime
                and record.data_source_id is not None
                and record.data_source_id == adjacent.data_source_id
            )

            if same_window:
                self.event_record_detail_repo.delete_by_record_id(db_session, adjacent.id)
                self.event_record_detail_repo.create_and_flush(
                    db_session,
                    detail.model_copy(update={"record_id": adjacent.id, **merged_detail_fields}),
                    detail_type="sleep",
                )
                db_session.commit()
                return adjacent, False, detail

            record = record.model_copy(
                update={
                    "id": uuid4(),
                    "start_datetime": merged_start,
                    "end_datetime": merged_end,
                    "duration_seconds": int((merged_end - merged_start).total_seconds()),
                }
            )
            created_record = self.crud.create_and_flush(db_session, record)

            if created_record.id == adjacent.id:
                # data_source_id was None (resolved at insert time) and the
                # constraint returned the existing row — treat as same_window.
                self.event_record_detail_repo.delete_by_record_id(db_session, adjacent.id)
                self.event_record_detail_repo.create_and_flush(
                    db_session,
                    detail.model_copy(update={"record_id": adjacent.id, **merged_detail_fields}),
                    detail_type="sleep",
                )
                db_session.commit()
                return adjacent, False, detail

            merged_final_detail = detail.model_copy(update={"record_id": created_record.id, **merged_detail_fields})
            self.event_record_detail_repo.create_and_flush(
                db_session,
                merged_final_detail,
                detail_type="sleep",
            )
            self.crud.delete_flush(db_session, adjacent)
            db_session.commit()
            return created_record, True, merged_final_detail

        created_record = self.crud.create_and_flush(db_session, record)
        new_detail = detail.model_copy(update={"record_id": created_record.id})
        self.event_record_detail_repo.create_and_flush(
            db_session,
            new_detail,
            detail_type="sleep",
        )
        db_session.commit()
        return created_record, True, new_detail

    @staticmethod
    def _emit_event_record_webhook(
        record: EventRecord,
        data_source: DataSource,
        detail: EventRecordDetailCreate,
    ) -> None:
        """Fire the appropriate outgoing webhook for a newly created event record."""
        category = (record.category or "").lower()
        provider = str(data_source.provider)
        device = data_source.device_model
        zone_offset = record.zone_offset
        if category == "sleep":
            eff = detail.sleep_efficiency_score
            has_stages = any(
                [
                    detail.sleep_awake_minutes,
                    detail.sleep_light_minutes,
                    detail.sleep_deep_minutes,
                    detail.sleep_rem_minutes,
                ]
            )
            on_sleep_created(
                record_id=record.id,
                user_id=data_source.user_id,
                provider=provider,
                device=device,
                start_time=record.start_datetime.isoformat(),
                end_time=record.end_datetime.isoformat(),
                zone_offset=zone_offset,
                duration_seconds=record.duration_seconds,
                efficiency_percent=float(eff) if eff is not None else None,
                stages={
                    "awake_minutes": detail.sleep_awake_minutes,
                    "light_minutes": detail.sleep_light_minutes,
                    "deep_minutes": detail.sleep_deep_minutes,
                    "rem_minutes": detail.sleep_rem_minutes,
                }
                if has_stages
                else None,
                is_nap=detail.is_nap,
            )
        elif category == "workout":
            avg_pace: int | None = None
            if detail.average_speed and float(detail.average_speed) > 0:
                avg_pace = int(1000 / float(detail.average_speed))
            on_workout_created(
                record_id=record.id,
                user_id=data_source.user_id,
                provider=provider,
                device=device,
                workout_type=record.type,
                start_time=record.start_datetime.isoformat(),
                end_time=record.end_datetime.isoformat(),
                zone_offset=zone_offset,
                duration_seconds=record.duration_seconds,
                calories_kcal=float(detail.energy_burned) if detail.energy_burned is not None else None,
                distance_meters=float(detail.distance) if detail.distance is not None else None,
                avg_heart_rate_bpm=int(detail.heart_rate_avg) if detail.heart_rate_avg is not None else None,
                max_heart_rate_bpm=int(detail.heart_rate_max) if detail.heart_rate_max is not None else None,
                elevation_gain_meters=float(detail.total_elevation_gain)
                if detail.total_elevation_gain is not None
                else None,
                avg_pace_sec_per_km=avg_pace,
            )

    def bulk_create(
        self,
        db_session: DbSession,
        records: list[EventRecordCreate],
    ) -> list[UUID]:
        """Bulk create event records with batch data source resolution."""
        # Webhooks are not emitted for bulk-created records; they fire via
        # create_detail() when individual details are added.
        return self.crud.bulk_create(db_session, records)

    def bulk_create_details(
        self,
        db_session: DbSession,
        details: list[EventRecordDetailCreate],
        detail_type: str = "workout",
    ) -> None:
        """Bulk create event record details."""
        self.event_record_detail_repo.bulk_create(db_session, details, detail_type=detail_type)  # type: ignore[arg-type]

    @handle_exceptions
    def _get_records_with_filters(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> tuple[list[tuple[EventRecord, DataSource]], int]:
        self.logger.debug(f"Fetching event records with filters: {query_params.model_dump()}")

        records, total_count = self.crud.get_records_with_filters(db_session, query_params, user_id)

        self.logger.debug(f"Retrieved {len(records)} event records out of {total_count} total")

        return records, total_count

    @handle_exceptions
    def get_records_response(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> list[EventRecordResponse]:
        records, _ = self._get_records_with_filters(db_session, query_params, user_id)

        return [self._build_response(record, data_source) for record, data_source in records]

    def get_count_by_workout_type(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of workouts grouped by workout type."""
        return self.crud.get_count_by_workout_type(db_session)

    def _map_source(self, data_source: DataSource) -> DataSourceSchema:
        return DataSourceSchema(
            provider=data_source.source or "unknown",
            device=data_source.device_model,
        )

    @handle_exceptions
    def get_workouts(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: EventRecordQueryParams,
    ) -> PaginatedResponse[Workout]:
        params.category = "workout"
        records, total_count = self._get_records_with_filters(db_session, params, str(user_id))
        # Ensure total_count is always an int (not None)
        total_count = total_count if total_count is not None else 0

        limit = params.limit or 20
        has_more = len(records) > limit

        # Check if this is backward pagination
        is_backward = params.cursor and params.cursor.startswith("prev_")

        # Trim to limit
        if has_more:
            records = records[-limit:] if is_backward else records[:limit]

        # Generate cursors
        next_cursor = None
        previous_cursor = None

        if records:
            # Always generate next_cursor if has_more
            if has_more:
                last_record, _ = records[-1]
                next_cursor = encode_cursor(last_record.start_datetime, last_record.id, "next")

            # Generate previous_cursor only if:
            # 1. We used a cursor to get here (not the first page)
            # 2. There are more items before (for backward) OR we're doing forward navigation
            if params.cursor:
                # For backward navigation: only set previous_cursor if has_more
                # For forward navigation: always set previous_cursor
                if is_backward:
                    if has_more:
                        first_record, _ = records[0]
                        previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")
                else:
                    first_record, _ = records[0]
                    previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")

        computed_hr = self._resolve_avg_hr(db_session, [r for r, _ in records])

        data = []
        for record, data_source in records:
            details: WorkoutDetails | None = record.detail if isinstance(record.detail, WorkoutDetails) else None

            workout = Workout(
                id=record.id,
                type=record.type or "unknown",
                name=None,  # Not in EventRecord currently
                start_time=record.start_datetime,
                end_time=record.end_datetime,
                zone_offset=record.zone_offset,
                duration_seconds=record.duration_seconds,
                source=self._map_source(data_source),
                calories_kcal=float(details.energy_burned) if details and details.energy_burned else None,
                distance_meters=float(details.distance) if details and details.distance else None,
                avg_heart_rate_bpm=computed_hr.get(record.id),
                max_heart_rate_bpm=details.heart_rate_max if details else None,
                avg_pace_sec_per_km=None,  # Derived or in details?
                elevation_gain_meters=float(details.total_elevation_gain)
                if details and details.total_elevation_gain
                else None,
            )
            data.append(workout)

        return PaginatedResponse(
            data=data,
            pagination=Pagination(
                has_more=has_more,
                next_cursor=next_cursor,
                previous_cursor=previous_cursor,
                total_count=total_count,
            ),
            metadata=TimeseriesMetadata(
                sample_count=len(data),
                start_time=params.start_datetime,
                end_time=params.end_datetime,
            ),
        )

    @handle_exceptions
    def get_workout_detailed(
        self,
        db_session: DbSession,
        user_id: UUID,
        workout_id: UUID,
    ) -> WorkoutDetailed | None:
        """Get a detailed workout record with all associated data."""
        record = self.crud.get_record_with_details(db_session, workout_id, "workout")

        if not record:
            return None

        data_source = self.data_source_repo.get(db_session, record.data_source_id)

        if not data_source or data_source.user_id != user_id:
            return None

        details: WorkoutDetails | None = record.detail if isinstance(record.detail, WorkoutDetails) else None

        if details and record.type in WORKOUTS_WITH_PACE:
            # Seconds per kilometer - speed is in meters per second
            if details.average_speed and details.average_speed > 0:
                avg_pace_sec_per_km = 1000 / details.average_speed
            elif details.distance > 0:
                avg_pace_sec_per_km = record.duration_seconds / details.distance * 1000
        else:
            avg_pace_sec_per_km = None

        return WorkoutDetailed(
            id=record.id,
            type=record.type or "unknown",
            name=None,
            start_time=record.start_datetime,
            end_time=record.end_datetime,
            zone_offset=record.zone_offset,
            duration_seconds=record.duration_seconds,
            source=self._map_source(data_source),
            calories_kcal=float(details.energy_burned) if details and details.energy_burned else None,
            distance_meters=float(details.distance) if details and details.distance else None,
            avg_heart_rate_bpm=self._resolve_avg_hr(db_session, [record]).get(record.id),
            max_heart_rate_bpm=details.heart_rate_max if details else None,
            avg_pace_sec_per_km=avg_pace_sec_per_km,
            elevation_gain_meters=float(details.total_elevation_gain)
            if details and details.total_elevation_gain
            else None,
            heart_rate_samples=[],  # TODO: Fetch from DataPointSeries if needed
        )

    @handle_exceptions
    def get_sleep_sessions(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: EventRecordQueryParams,
    ) -> PaginatedResponse[SleepSession]:
        params.category = "sleep"
        records, total_count = self._get_records_with_filters(db_session, params, str(user_id))
        # Ensure total_count is always an int (not None)
        total_count = total_count if total_count is not None else 0

        limit = params.limit or 20
        has_more = len(records) > limit

        # Check if this is backward pagination
        is_backward = params.cursor and params.cursor.startswith("prev_")

        # Trim to limit
        if has_more:
            records = records[-limit:] if is_backward else records[:limit]

        # Generate cursors
        next_cursor = None
        previous_cursor = None

        if records:
            # Always generate next_cursor if has_more
            if has_more:
                last_record, _ = records[-1]
                next_cursor = encode_cursor(last_record.start_datetime, last_record.id, "next")

            # Generate previous_cursor only if:
            # 1. We used a cursor to get here (not the first page)
            # 2. There are more items before (for backward) OR we're doing forward navigation
            if params.cursor:
                # For backward navigation: only set previous_cursor if has_more
                # For forward navigation: always set previous_cursor
                if is_backward:
                    if has_more:
                        first_record, _ = records[0]
                        previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")
                else:
                    first_record, _ = records[0]
                    previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")

        data = []
        for record, data_source in records:
            details: SleepDetails | None = record.detail if isinstance(record.detail, SleepDetails) else None

            session = SleepSession(
                id=record.id,
                start_time=record.start_datetime,
                end_time=record.end_datetime,
                zone_offset=record.zone_offset,
                source=self._map_source(data_source),
                duration_seconds=record.duration_seconds or 0,
                efficiency_percent=float(details.sleep_efficiency_score)
                if details and details.sleep_efficiency_score
                else None,
                is_nap=details.is_nap if (details and details.is_nap is not None) else False,
                sleep_stage_intervals=details.sleep_stages if details else None,
                stages=SleepStagesSummary(
                    deep_minutes=details.sleep_deep_minutes or 0 if details else 0,
                    light_minutes=details.sleep_light_minutes or 0 if details else 0,
                    rem_minutes=details.sleep_rem_minutes or 0 if details else 0,
                    awake_minutes=details.sleep_awake_minutes or 0 if details else 0,
                )
                if details
                else None,
            )
            data.append(session)

        return PaginatedResponse(
            data=data,
            pagination=Pagination(
                has_more=has_more,
                next_cursor=next_cursor,
                previous_cursor=previous_cursor,
                total_count=total_count,
            ),
            metadata=TimeseriesMetadata(
                sample_count=len(data),
                start_time=params.start_datetime,
                end_time=params.end_datetime,
            ),
        )


event_record_service = EventRecordService(log=getLogger(__name__))
