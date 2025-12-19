from datetime import datetime, time, timezone
from uuid import UUID

import isodate
from sqlalchemy import and_, asc, desc, func, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.repositories.repositories import CrudRepository
from app.schemas import EventRecordCreate, EventRecordQueryParams, EventRecordUpdate
from app.utils.exceptions import InvalidCursorError, handle_exceptions
from app.utils.dates import parse_query_datetime


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

        if query_params.start_date:
            # Handle both date (YYYY-MM-DD) and datetime (YYYY-MM-DDTHH:MM:SS) formats
            try:
                start_dt = isodate.parse_datetime(query_params.start_date)
            except isodate.ISO8601Error:
                # If it's just a date, parse it and set time to start of day
                start_dt = isodate.parse_date(query_params.start_date)
            filters.append(EventRecord.start_datetime >= start_dt)

        if query_params.end_date:
            # Handle both date (YYYY-MM-DD) and datetime (YYYY-MM-DDTHH:MM:SS) formats
            try:
                end_dt = isodate.parse_datetime(query_params.end_date)
            except isodate.ISO8601Error:
                # If it's just a date, parse it and set time to end of day
                date_only = isodate.parse_date(query_params.end_date)
                end_dt = datetime.combine(date_only, time.max, tzinfo=timezone.utc)
            filters.append(EventRecord.end_datetime <= end_dt)

        if query_params.min_duration is not None:
            filters.append(EventRecord.duration_seconds >= query_params.min_duration)

        if query_params.max_duration is not None:
            filters.append(EventRecord.duration_seconds <= query_params.max_duration)

        if filters:
            query = query.filter(and_(*filters))

        # Determine sort column and direction (used for both cursor and ordering)
        sort_by = query_params.sort_by or "start_datetime"
        sort_column = getattr(EventRecord, sort_by)
        is_asc = query_params.sort_order == "asc"

        # Cursor pagination (keyset) - replaces offset-based pagination
        if query_params.cursor:
            # Expected cursor format: "timestamp_iso|id"
            try:
                cursor_ts_str, cursor_id_str = query_params.cursor.split("|")
                cursor_ts = parse_query_datetime(cursor_ts_str)
                cursor_id = UUID(cursor_id_str)
            except (ValueError, TypeError, isodate.ISO8601Error):
                raise InvalidCursorError(cursor=query_params.cursor)

            if sort_by == "start_datetime":
                # WHERE (start_datetime, id) > (cursor_ts, cursor_id) for ASC, < for DESC
                comparison = (
                    tuple_(EventRecord.start_datetime, EventRecord.id) > (cursor_ts, cursor_id)
                    if is_asc
                    else tuple_(EventRecord.start_datetime, EventRecord.id) < (cursor_ts, cursor_id)
                )
                query = query.filter(comparison)
            else:
                # For other sort columns, fall back to simple ID-based cursor
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
