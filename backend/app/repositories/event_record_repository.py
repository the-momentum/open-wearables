from datetime import datetime
from uuid import UUID

from sqlalchemy import UUID as SQL_UUID
from sqlalchemy import Date, Integer, String, and_, asc, case, cast, desc, func, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, selectinload

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping, SleepDetails
from app.models.workout_details import WorkoutDetails
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
                    self.model.end_datetime == creation.end_datetime,
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
        query: Query = (
            db_session.query(EventRecord, ExternalDeviceMapping)
            .join(
                ExternalDeviceMapping,
                EventRecord.external_device_mapping_id == ExternalDeviceMapping.id,
            )
            .options(selectinload(EventRecord.detail))
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
            filters.append(EventRecord.end_datetime < query_params.end_datetime)

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

        # Calculate total count BEFORE applying cursor filters
        # This gives us the total matching records (after all other filters)
        total_count = query.count()

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
                return list(reversed(results)), total_count

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

    def get_sleep_summaries(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        cursor: str | None,
        limit: int,
    ) -> list[dict]:
        """Get daily sleep summaries aggregated by date, provider, and device.

        Returns list of dicts with keys:
        - sleep_date, min_start_time, max_end_time, total_duration_minutes
        - provider_name, device_id, record_id
        - time_in_bed_minutes, efficiency_percent
        - deep_minutes, light_minutes, rem_minutes, awake_minutes
        - nap_count, nap_duration_minutes
        """
        # Helper: condition for "is NOT a nap" (main sleep)
        # is_nap can be True, False, or NULL - we treat NULL as "not a nap"
        is_main_sleep = func.coalesce(SleepDetails.is_nap, False) == False  # noqa: E712

        # Build base aggregated query as subquery
        # Join with SleepDetails to get sleep stage data
        # Cast UUID to text for min() since PostgreSQL doesn't support min() on UUID directly
        subquery = (
            db_session.query(
                cast(EventRecord.end_datetime, Date).label("sleep_date"),
                # Main sleep times (exclude naps)
                func.min(case((is_main_sleep, EventRecord.start_datetime), else_=None)).label("min_start_time"),
                func.max(case((is_main_sleep, EventRecord.end_datetime), else_=None)).label("max_end_time"),
                # Main sleep duration (exclude naps)
                func.sum(case((is_main_sleep, EventRecord.duration_seconds), else_=0)).label("total_duration"),
                ExternalDeviceMapping.provider_name,
                ExternalDeviceMapping.device_id,
                func.min(cast(EventRecord.id, String)).label("record_id_text"),
                # Sleep details aggregations - main sleep only (minutes stored, convert to seconds later)
                func.sum(case((is_main_sleep, SleepDetails.sleep_time_in_bed_minutes), else_=None)).label(
                    "time_in_bed_minutes"
                ),
                func.sum(case((is_main_sleep, SleepDetails.sleep_deep_minutes), else_=None)).label("deep_minutes"),
                func.sum(case((is_main_sleep, SleepDetails.sleep_light_minutes), else_=None)).label("light_minutes"),
                func.sum(case((is_main_sleep, SleepDetails.sleep_rem_minutes), else_=None)).label("rem_minutes"),
                func.sum(case((is_main_sleep, SleepDetails.sleep_awake_minutes), else_=None)).label("awake_minutes"),
                # Weighted average for efficiency - main sleep only (weight by duration)
                func.sum(
                    case(
                        (is_main_sleep, SleepDetails.sleep_efficiency_score * EventRecord.duration_seconds),
                        else_=None,
                    )
                ).label("efficiency_weighted_sum"),
                func.sum(
                    case(
                        (
                            and_(is_main_sleep, SleepDetails.sleep_efficiency_score != None),  # noqa: E711
                            EventRecord.duration_seconds,
                        ),
                        else_=0,
                    )
                ).label("efficiency_duration_sum"),
                # Nap aggregations
                func.sum(
                    cast(SleepDetails.is_nap == True, Integer)  # noqa: E712
                ).label("nap_count"),
                func.sum(
                    case((SleepDetails.is_nap == True, EventRecord.duration_seconds), else_=0)  # noqa: E712
                ).label("nap_duration"),
            )
            .join(ExternalDeviceMapping, EventRecord.external_device_mapping_id == ExternalDeviceMapping.id)
            .outerjoin(SleepDetails, SleepDetails.record_id == EventRecord.id)
            .filter(
                ExternalDeviceMapping.user_id == user_id,
                EventRecord.category == "sleep",
                EventRecord.end_datetime >= start_date,
                cast(EventRecord.end_datetime, Date) < cast(end_date, Date),
            )
            .group_by(
                cast(EventRecord.end_datetime, Date),
                ExternalDeviceMapping.provider_name,
                ExternalDeviceMapping.device_id,
            )
        ).subquery()

        # Build main query from subquery, casting record_id back to UUID
        record_id_col = cast(subquery.c.record_id_text, SQL_UUID).label("record_id")
        query = db_session.query(
            subquery.c.sleep_date,
            subquery.c.min_start_time,
            subquery.c.max_end_time,
            subquery.c.total_duration,
            subquery.c.provider_name,
            subquery.c.device_id,
            record_id_col,
            subquery.c.time_in_bed_minutes,
            subquery.c.deep_minutes,
            subquery.c.light_minutes,
            subquery.c.rem_minutes,
            subquery.c.awake_minutes,
            subquery.c.efficiency_weighted_sum,
            subquery.c.efficiency_duration_sum,
            subquery.c.nap_count,
            subquery.c.nap_duration,
        )

        # Handle cursor pagination
        if cursor:
            cursor_ts, cursor_id, direction = decode_cursor(cursor)
            cursor_date = cursor_ts.date()

            if direction == "prev":
                # Backward pagination: get items BEFORE cursor
                query = query.filter(tuple_(subquery.c.sleep_date, record_id_col) < (cursor_date, cursor_id))
                query = query.order_by(desc(subquery.c.sleep_date), desc(record_id_col))
            else:
                # Forward pagination: get items AFTER cursor
                query = query.filter(tuple_(subquery.c.sleep_date, record_id_col) > (cursor_date, cursor_id))
                query = query.order_by(asc(subquery.c.sleep_date), asc(record_id_col))
        else:
            # No cursor: default ordering
            query = query.order_by(asc(subquery.c.sleep_date), asc(record_id_col))

        # Limit + 1 to check for has_more
        results = query.limit(limit + 1).all()

        # Transform results to dict format
        summaries = []
        for row in results:
            # Calculate weighted average efficiency
            efficiency_percent = None
            if row.efficiency_duration_sum and row.efficiency_duration_sum > 0:
                efficiency_percent = float(row.efficiency_weighted_sum) / float(row.efficiency_duration_sum)

            summaries.append(
                {
                    "sleep_date": row.sleep_date,
                    "min_start_time": row.min_start_time,
                    "max_end_time": row.max_end_time,
                    "total_duration_minutes": int(row.total_duration or 0) // 60,
                    "provider_name": row.provider_name,
                    "device_id": row.device_id,
                    "record_id": row.record_id,
                    "time_in_bed_minutes": int(row.time_in_bed_minutes)
                    if row.time_in_bed_minutes is not None
                    else None,
                    "deep_minutes": int(row.deep_minutes) if row.deep_minutes is not None else None,
                    "light_minutes": int(row.light_minutes) if row.light_minutes is not None else None,
                    "rem_minutes": int(row.rem_minutes) if row.rem_minutes is not None else None,
                    "awake_minutes": int(row.awake_minutes) if row.awake_minutes is not None else None,
                    "efficiency_percent": efficiency_percent,
                    # Nap tracking
                    "nap_count": int(row.nap_count) if row.nap_count is not None else None,
                    "nap_duration_minutes": int(row.nap_duration) // 60 if row.nap_duration is not None else None,
                }
            )
        return summaries

    def get_daily_workout_aggregates(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """Get daily workout aggregates including elevation, distance, and energy.

        Aggregates WorkoutDetails data by date for activity summaries.

        Returns list of dicts with keys:
        - workout_date, provider_name, device_id
        - elevation_meters, distance_meters, energy_burned_kcal
        """
        results = (
            db_session.query(
                cast(self.model.end_datetime, Date).label("workout_date"),
                ExternalDeviceMapping.provider_name,
                ExternalDeviceMapping.device_id,
                # Sum elevation gain for all workouts on that day
                func.sum(WorkoutDetails.total_elevation_gain).label("elevation_sum"),
                # Sum distance for all workouts
                func.sum(WorkoutDetails.distance).label("distance_sum"),
                # Sum energy burned
                func.sum(WorkoutDetails.energy_burned).label("energy_sum"),
            )
            .join(ExternalDeviceMapping, self.model.external_device_mapping_id == ExternalDeviceMapping.id)
            # Use outerjoin since WorkoutDetails is optional - some workouts may not have details
            .outerjoin(WorkoutDetails, self.model.id == WorkoutDetails.record_id)
            .filter(
                ExternalDeviceMapping.user_id == user_id,
                self.model.category == "workout",
                self.model.end_datetime >= start_date,
                cast(self.model.end_datetime, Date) < cast(end_date, Date),
            )
            .group_by(
                cast(self.model.end_datetime, Date),
                ExternalDeviceMapping.provider_name,
                ExternalDeviceMapping.device_id,
            )
            .order_by(asc(cast(self.model.end_datetime, Date)))
            .all()
        )

        aggregates = []
        for row in results:
            aggregates.append(
                {
                    "workout_date": row.workout_date,
                    "provider_name": row.provider_name,
                    "device_id": row.device_id,
                    "elevation_meters": float(row.elevation_sum) if row.elevation_sum is not None else None,
                    "distance_meters": float(row.distance_sum) if row.distance_sum is not None else None,
                    "energy_burned_kcal": float(row.energy_sum) if row.energy_sum is not None else None,
                }
            )
        return aggregates
