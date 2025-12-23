from uuid import UUID

from sqlalchemy import and_, asc, desc, func, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.repositories.repositories import CrudRepository
from app.schemas import EventRecordCreate, EventRecordQueryParams, EventRecordUpdate
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import decode_cursor


class EventRecordRepository(
    CrudRepository[EventRecord, EventRecordCreate, EventRecordUpdate],
):
    def __init__(self, model: type[EventRecord]):
        super().__init__(model)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)

    @handle_exceptions
    def create(self, db_session: DbSession, creator: EventRecordCreate) -> EventRecord:
        # Use provider_name for external mapping (e.g., 'suunto')
        # provider_id is the workout/record ID from the provider
        mapping = self.mapping_repo.ensure_mapping(
            db_session,
            creator.user_id,
            creator.provider_name or "unknown",  # Provider name for mapping (suunto/garmin/polar)
            creator.device_id,
            creator.external_device_mapping_id,
        )

        creation_data = creator.model_dump()
        creation_data["external_device_mapping_id"] = mapping.id
        for redundant_key in ("user_id", "provider_name", "device_id"):
            creation_data.pop(redundant_key, None)

        creation = self.model(**creation_data)

        try:
            db_session.add(creation)
            db_session.commit()
            db_session.refresh(creation)
            return creation
        except IntegrityError:
            db_session.rollback()
            # Query using the mapping and other unique constraint fields
            existing = (
                db_session.query(self.model)
                .filter(
                    self.model.external_device_mapping_id == mapping.id,
                    self.model.start_datetime == creation.start_datetime,
                    self.model.category == creation.category,
                )
                .one_or_none()
            )
            if existing:
                return existing
            raise

    def get_records_with_filters(
        self,
        db_session: DbSession,
        query_params: EventRecordQueryParams,
        user_id: str,
    ) -> tuple[list[tuple[EventRecord, ExternalDeviceMapping]], int]:
        query: Query = db_session.query(EventRecord, ExternalDeviceMapping).join(
            ExternalDeviceMapping,
            EventRecord.external_device_mapping_id == ExternalDeviceMapping.id,
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

        if getattr(query_params, "provider_name", None):
            filters.append(ExternalDeviceMapping.provider_name == query_params.provider_name)

        if getattr(query_params, "external_device_mapping_id", None):
            filters.append(EventRecord.external_device_mapping_id == query_params.external_device_mapping_id)

        if query_params.start_datetime:
            filters.append(EventRecord.start_datetime >= query_params.start_datetime)

        if query_params.end_datetime:
            filters.append(EventRecord.end_datetime <= query_params.end_datetime)

        if query_params.min_duration is not None:
            filters.append(EventRecord.duration_seconds >= query_params.min_duration)

        if query_params.max_duration is not None:
            filters.append(EventRecord.duration_seconds <= query_params.max_duration)

        if filters:
            query = query.filter(and_(*filters))

        # Determine sort column and direction
        sort_by = query_params.sort_by or "start_datetime"
        sort_column = getattr(EventRecord, sort_by)
        is_asc = query_params.sort_order == "asc"

        # Cursor pagination (keyset)
        if query_params.cursor:
            cursor_ts, cursor_id, direction = decode_cursor(query_params.cursor)

            if direction == "prev":
                # Backward pagination: get items BEFORE cursor
                if sort_by == "start_datetime":
                    comparison = (
                        tuple_(EventRecord.start_datetime, EventRecord.id) < (cursor_ts, cursor_id)
                        if is_asc
                        else tuple_(EventRecord.start_datetime, EventRecord.id) > (cursor_ts, cursor_id)
                    )
                    query = query.filter(comparison)
                else:
                    query = query.filter(EventRecord.id < cursor_id if is_asc else EventRecord.id > cursor_id)

                # Reverse sort order for backward pagination
                sort_order = desc if is_asc else asc
                query = query.order_by(sort_order(sort_column), sort_order(EventRecord.id))

                # Limit + 1 to check for previous page
                limit = query_params.limit or 20
                results = query.limit(limit + 1).all()
                # Reverse to get correct order
                return list(reversed(results)), query.count()

            # Forward pagination: get items AFTER cursor
            if sort_by == "start_datetime":
                comparison = (
                    tuple_(EventRecord.start_datetime, EventRecord.id) > (cursor_ts, cursor_id)
                    if is_asc
                    else tuple_(EventRecord.start_datetime, EventRecord.id) < (cursor_ts, cursor_id)
                )
                query = query.filter(comparison)
            else:
                query = query.filter(EventRecord.id > cursor_id if is_asc else EventRecord.id < cursor_id)

        total_count = query.count()

        # Apply ordering (ID as secondary sort for deterministic pagination)
        sort_order = asc if is_asc else desc
        query = query.order_by(sort_order(sort_column), sort_order(EventRecord.id))

        # Limit + 1 to check for next page (cursor pagination)
        limit = query_params.limit or 20

        # When using cursor, we don't use offset (keyset pagination)
        if not query_params.cursor and query_params.offset:
            query = query.offset(query_params.offset)

        return query.limit(limit + 1).all(), total_count

    def get_count_by_workout_type(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of workouts grouped by workout type.

        Returns list of (workout_type, count) tuples ordered by count descending.
        Only includes records with category='workout'.
        """

        results = (
            db_session.query(self.model.type, func.count(self.model.id).label("count"))
            .filter(self.model.category == "workout")
            .group_by(self.model.type)
            .order_by(func.count(self.model.id).desc())
            .all()
        )
        return [(workout_type, count) for workout_type, count in results]
