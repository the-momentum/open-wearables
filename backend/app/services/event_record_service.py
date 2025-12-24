from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import (
    EventRecord,
    EventRecordDetail,
    ExternalDeviceMapping,
    SleepDetails,
    WorkoutDetails,
)
from app.repositories import EventRecordDetailRepository, EventRecordRepository
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordQueryParams,
    EventRecordResponse,
    EventRecordUpdate,
)
from app.schemas.common_types import DataSource, PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.events import (
    SleepSession,
    Workout,
    WorkoutDetailed,
)
from app.schemas.summaries import SleepStagesSummary
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

    def _build_response(
        self,
        record: EventRecord,
        mapping: ExternalDeviceMapping,
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
            external_device_mapping_id=record.external_device_mapping_id,
            user_id=mapping.user_id,
            provider_name=mapping.provider_name,
            device_id=mapping.device_id,
        )

    def create_detail(
        self,
        db_session: DbSession,
        detail: EventRecordDetailCreate,
        detail_type: str = "workout",
    ) -> EventRecordDetail:
        return self.event_record_detail_repo.create(db_session, detail, detail_type=detail_type)  # type: ignore[return-value]

    @handle_exceptions
    async def _get_records_with_filters(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> tuple[list[tuple[EventRecord, ExternalDeviceMapping]], int]:
        self.logger.debug(f"Fetching event records with filters: {query_params.model_dump()}")

        records, total_count = self.crud.get_records_with_filters(db_session, query_params, user_id)

        self.logger.debug(f"Retrieved {len(records)} event records out of {total_count} total")

        return records, total_count

    @handle_exceptions
    async def get_records_response(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> list[EventRecordResponse]:
        records, _ = await self._get_records_with_filters(db_session, query_params, user_id)

        return [self._build_response(record, mapping) for record, mapping in records]

    def get_count_by_workout_type(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of workouts grouped by workout type."""
        return self.crud.get_count_by_workout_type(db_session)

    def _map_source(self, mapping: ExternalDeviceMapping) -> DataSource:
        return DataSource(
            provider=mapping.provider_name or "unknown",
            device=mapping.device_id,
        )

    @handle_exceptions
    async def get_workouts(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: EventRecordQueryParams,
    ) -> PaginatedResponse[Workout]:
        params.category = "workout"
        records, total_count = await self._get_records_with_filters(db_session, params, str(user_id))
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
        for record, mapping in records:
            details: WorkoutDetails | None = record.detail if isinstance(record.detail, WorkoutDetails) else None

            workout = Workout(
                id=record.id,
                type=record.type or "unknown",
                name=None,  # Not in EventRecord currently
                start_time=record.start_datetime,
                end_time=record.end_datetime,
                duration_seconds=record.duration_seconds,
                source=self._map_source(mapping),
                calories_kcal=None,  # Need to check where this is stored,
                # likely in details but not in WorkoutDetails definition I saw earlier?
                distance_meters=None,
                avg_heart_rate_bpm=int(details.heart_rate_avg) if details and details.heart_rate_avg else None,
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
    async def get_workout_detailed(
        self,
        db_session: DbSession,
        user_id: UUID,
        workout_id: UUID,
    ) -> WorkoutDetailed | None:
        # Fetch the record with details
        # This is a simplified fetch, ideally we should have a dedicated repo method
        record = (
            db_session.query(EventRecord)
            .filter(EventRecord.id == workout_id, EventRecord.category == "workout")
            .first()
        )

        if not record:
            return None

        # Ensure user matches (security check)
        mapping = (
            db_session.query(ExternalDeviceMapping)
            .filter(ExternalDeviceMapping.id == record.external_mapping_id, ExternalDeviceMapping.user_id == user_id)
            .first()
        )

        if not mapping:
            return None

        details: WorkoutDetails | None = record.detail if isinstance(record.detail, WorkoutDetails) else None

        return WorkoutDetailed(
            id=record.id,
            type=record.type or "unknown",
            name=None,
            start_time=record.start_datetime,
            end_time=record.end_datetime,
            duration_seconds=record.duration_seconds,
            source=self._map_source(mapping),
            calories_kcal=None,
            distance_meters=None,
            avg_heart_rate_bpm=int(details.heart_rate_avg) if details and details.heart_rate_avg else None,
            max_heart_rate_bpm=details.heart_rate_max if details else None,
            avg_pace_sec_per_km=None,
            elevation_gain_meters=float(details.total_elevation_gain)
            if details and details.total_elevation_gain
            else None,
            heart_rate_samples=[],  # TODO: Fetch from DataPointSeries if needed
        )

    @handle_exceptions
    async def get_sleep_sessions(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: EventRecordQueryParams,
    ) -> PaginatedResponse[SleepSession]:
        params.category = "sleep"
        records, total_count = await self._get_records_with_filters(db_session, params, str(user_id))
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
        for record, mapping in records:
            details: SleepDetails | None = record.detail if isinstance(record.detail, SleepDetails) else None

            session = SleepSession(
                id=record.id,
                start_time=record.start_datetime,
                end_time=record.end_datetime,
                source=self._map_source(mapping),
                duration_seconds=record.duration_seconds or 0,
                efficiency_percent=float(details.sleep_efficiency_score)
                if details and details.sleep_efficiency_score
                else None,
                is_nap=details.is_nap if (details and details.is_nap is not None) else False,
                stages=SleepStagesSummary(
                    deep_seconds=(details.sleep_deep_minutes or 0) * 60 if details else 0,
                    light_seconds=(details.sleep_light_minutes or 0) * 60 if details else 0,
                    rem_seconds=(details.sleep_rem_minutes or 0) * 60 if details else 0,
                    awake_seconds=(details.sleep_awake_minutes or 0) * 60 if details else 0,
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
