from logging import Logger, getLogger

from app.database import DbSession
from app.models import EventRecord, EventRecordDetail, ExternalDeviceMapping
from app.repositories import EventRecordDetailRepository, EventRecordRepository
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordQueryParams,
    EventRecordResponse,
    EventRecordUpdate,
)
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


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
            category=record.category,
            type=record.type,
            source_name=record.source_name,
            duration_seconds=record.duration_seconds,
            start_datetime=record.start_datetime,
            end_datetime=record.end_datetime,
            external_mapping_id=record.external_mapping_id,
            user_id=mapping.user_id,
            provider_id=mapping.provider_id,
            device_id=mapping.device_id,
        )

    def create_detail(self, db_session: DbSession, detail: EventRecordDetailCreate) -> EventRecordDetail:
        return self.event_record_detail_repo.create(db_session, detail)

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


event_record_service = EventRecordService(log=getLogger(__name__))
