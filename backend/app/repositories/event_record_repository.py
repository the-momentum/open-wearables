from uuid import UUID

import isodate
from sqlalchemy import and_, desc
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.repositories.repositories import CrudRepository
from app.schemas import EventRecordCreate, EventRecordQueryParams, EventRecordUpdate


class EventRecordRepository(
    CrudRepository[EventRecord, EventRecordCreate, EventRecordUpdate],
):
    def __init__(self, model: type[EventRecord]):
        super().__init__(model)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)

    def create(self, db_session: DbSession, creator: EventRecordCreate) -> EventRecord:
        mapping = self.mapping_repo.ensure_mapping(
            db_session,
            creator.user_id,
            creator.provider_id,
            creator.device_id,
            creator.external_mapping_id,
        )

        creation_data = creator.model_dump()
        creation_data["external_mapping_id"] = mapping.id
        for redundant_key in ("user_id", "provider_id", "device_id"):
            creation_data.pop(redundant_key, None)

        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def get_records_with_filters(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> tuple[list[tuple[EventRecord, ExternalDeviceMapping]], int]:
        query: Query = db_session.query(EventRecord, ExternalDeviceMapping).join(
            ExternalDeviceMapping,
            EventRecord.external_mapping_id == ExternalDeviceMapping.id,
        )

        filters = [ExternalDeviceMapping.user_id == UUID(user_id)]

        if query_params.category:
            filters.append(EventRecord.category == query_params.category)

        if query_params.record_type:
            filters.append(EventRecord.type.ilike(f"%{query_params.record_type}%"))

        if query_params.source_name:
            filters.append(EventRecord.source_name.ilike(f"%{query_params.source_name}%"))

        if query_params.device_id:
            filters.append(ExternalDeviceMapping.device_id == query_params.device_id)

        if getattr(query_params, "provider_id", None):
            filters.append(ExternalDeviceMapping.provider_id == query_params.provider_id)

        if getattr(query_params, "external_mapping_id", None):
            filters.append(EventRecord.external_mapping_id == query_params.external_mapping_id)

        if query_params.start_date:
            start_dt = isodate.parse_datetime(query_params.start_date)
            filters.append(EventRecord.start_datetime >= start_dt)

        if query_params.end_date:
            end_dt = isodate.parse_datetime(query_params.end_date)
            filters.append(EventRecord.end_datetime <= end_dt)

        if query_params.min_duration is not None:
            filters.append(EventRecord.duration_seconds >= query_params.min_duration)

        if query_params.max_duration is not None:
            filters.append(EventRecord.duration_seconds <= query_params.max_duration)

        if filters:
            query = query.filter(and_(*filters))

        total_count = query.count()

        sort_column = getattr(EventRecord, query_params.sort_by or "start_datetime")
        order_column = sort_column if query_params.sort_order == "asc" else desc(sort_column)

        paged_query = query.order_by(order_column).offset(query_params.offset).limit(query_params.limit)

        return paged_query.all(), total_count
