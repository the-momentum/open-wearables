import contextlib
from datetime import datetime
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import Date, String, asc, case, cast, func, literal_column, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

from app.database import DbSession
from app.models import DataPointSeries, DataSource, DeviceTypePriority, ProviderPriority
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.repositories import CrudRepository
from app.schemas import (
    ActiveMinutesResult,
    ActivityAggregateResult,
    IntensityMinutesResult,
    ProviderName,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.series_types import SeriesType, get_series_type_from_id, get_series_type_id
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import decode_cursor

# Identity tuple: (user_id, device_model, source)
DataSourceIdentity = tuple[UUID, str | None, str | None]


class DataPointSeriesRepository(
    CrudRepository[DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Repository for unified device data point series."""

    def __init__(self, model: type[DataPointSeries]):
        super().__init__(model)
        self.data_source_repo = DataSourceRepository()

    @handle_exceptions
    def create(self, db_session: DbSession, creator: TimeSeriesSampleCreate) -> DataPointSeries:
        """Create a data point sample, or return existing if duplicate.

        Handles duplicate records gracefully by catching IntegrityError and
        returning the existing record instead.
        """
        data_source = self.create_data_source(db_session, creator)

        creation_data = creator.model_dump()

        # Remove schema-only fields before creating the model
        for redundant_key in (
            "user_id",
            "source",
            "device_model",
            "provider",
            "user_connection_id",
            "software_version",
            "series_type",
            "data_source_id",
        ):
            creation_data.pop(redundant_key, None)

        # Set the proper values
        creation_data["data_source_id"] = data_source.id
        creation_data["series_type_definition_id"] = get_series_type_id(creator.series_type)

        creation = self.model(**creation_data)
        db_session.add(creation)
        return self.try_commit(db_session, creation)

    @handle_exceptions
    def bulk_create(self, db_session: DbSession, creators: list[TimeSeriesSampleCreate]) -> list[DataPointSeries]:
        """Bulk create data point samples.

        Optimized for performance:
        - Resolves data sources efficiently (batch fetch + batch insert missing)
        - Inserts data points in a single batch
        """
        if not creators:
            return []

        # 1. Resolve all data sources in batch
        identity_to_source_id = self._resolve_data_sources(db_session, creators)

        # 2. Build and execute data point batch insert
        self._insert_data_points(db_session, creators, identity_to_source_id)

        # Return empty list (ON CONFLICT DO NOTHING means strict tracking is omitted)
        return []

    def _resolve_data_sources(
        self, db_session: DbSession, creators: list[TimeSeriesSampleCreate]
    ) -> dict[DataSourceIdentity, UUID]:
        by_provider: dict[ProviderName, list[TimeSeriesSampleCreate]] = {}
        for c in creators:
            provider = self.data_source_repo.infer_provider_from_source(c.source)
            if c.provider:
                with contextlib.suppress(ValueError):
                    provider = ProviderName(c.provider)
            by_provider.setdefault(provider, []).append(c)

        identity_to_source_id: dict[DataSourceIdentity, UUID] = {}

        for provider, provider_creators in by_provider.items():
            unique_identities: set[DataSourceIdentity] = set()
            user_connection_id = provider_creators[0].user_connection_id if provider_creators else None
            for c in provider_creators:
                unique_identities.add((c.user_id, c.device_model, c.source))

            batch_result = self.data_source_repo.batch_ensure_data_sources(
                db_session, provider, user_connection_id, unique_identities
            )
            identity_to_source_id.update(batch_result)

        return identity_to_source_id

    def _insert_data_points(
        self,
        db_session: DbSession,
        creators: list[TimeSeriesSampleCreate],
        source_map: dict[DataSourceIdentity, UUID],
    ) -> None:
        """Batch insert data points."""
        values_list = []
        for creator in creators:
            identity: DataSourceIdentity = (creator.user_id, creator.device_model, creator.source)
            source_id = source_map.get(identity)

            if not source_id:
                # Should not happen if resolve logic is correct, but safe skip
                continue

            values_list.append(
                {
                    "id": creator.id,
                    "external_id": creator.external_id,
                    "data_source_id": source_id,
                    "recorded_at": creator.recorded_at,
                    "value": creator.value,
                    "series_type_definition_id": get_series_type_id(creator.series_type),
                }
            )

        if values_list:
            stmt = (
                insert(self.model)
                .values(values_list)
                .on_conflict_do_nothing(index_elements=["data_source_id", "series_type_definition_id", "recorded_at"])
            )
            db_session.execute(stmt)
            # NOTE: Caller should commit - allows batching multiple operations

    def try_commit(self, db_session: DbSession, creation: DataPointSeries) -> DataPointSeries:
        try:
            db_session.commit()
            db_session.refresh(creation)
            return creation
        except SQLAIntegrityError as e:
            if isinstance(e.orig, UniqueViolation):
                db_session.rollback()

                # Query for existing record using the unique constraint fields
                existing = (
                    db_session.query(self.model)
                    .filter(
                        self.model.data_source_id == creation.data_source_id,
                        self.model.series_type_definition_id == creation.series_type_definition_id,
                        self.model.recorded_at == creation.recorded_at,
                    )
                    .first()
                )

                if existing:
                    return existing
            # Re-raise if not a duplicate or if existing record not found
            raise

    def create_data_source(self, db_session: DbSession, creator: TimeSeriesSampleCreate) -> DataSource:
        provider = self.data_source_repo.infer_provider_from_source(creator.source)
        if creator.provider:
            with contextlib.suppress(ValueError):
                provider = ProviderName(creator.provider)

        return self.data_source_repo.ensure_data_source(
            db_session,
            user_id=creator.user_id,
            provider=provider,
            user_connection_id=creator.user_connection_id,
            device_model=creator.device_model,
            software_version=creator.software_version,
            source=creator.source,
        )

    def get_samples(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
    ) -> tuple[list[tuple[DataPointSeries, DataSource]], int]:
        """Get data points with filtering and keyset pagination.

        Returns a tuple of (samples, total_count) where total_count is calculated
        BEFORE applying cursor pagination, giving the total number of matching records.
        """
        query = (
            db_session.query(self.model, DataSource)
            .join(
                DataSource,
                self.model.data_source_id == DataSource.id,
            )
            .filter(DataSource.user_id == user_id)
        )

        if types:
            type_ids = [get_series_type_id(t) for t in types]
            query = query.filter(self.model.series_type_definition_id.in_(type_ids))

        if params.device_model:
            query = query.filter(DataSource.device_model == params.device_model)

        if params.source:
            query = query.filter(DataSource.source == params.source)

        if params.start_datetime:
            query = query.filter(self.model.recorded_at >= params.start_datetime)

        if params.end_datetime:
            query = query.filter(self.model.recorded_at < params.end_datetime)

        # Calculate total count BEFORE applying cursor pagination
        # This gives us the total matching records (after all other filters)
        total_count = query.count()

        # Cursor pagination (keyset)
        if params.cursor:
            cursor_ts, cursor_id, direction = decode_cursor(params.cursor)

            if direction == "prev":
                # Backward pagination: get items BEFORE cursor
                query = query.filter(
                    tuple_(self.model.recorded_at, self.model.id) < (cursor_ts, cursor_id),
                )
                query = query.order_by(self.model.recorded_at.desc(), self.model.id.desc())
                # Limit + 1 to check for previous page
                limit = params.limit or 50
                results = query.limit(limit + 1).all()
                # Reverse to get correct order
                return list(reversed(results)), total_count
            # Forward pagination: get items AFTER cursor
            query = query.filter(
                tuple_(self.model.recorded_at, self.model.id) > (cursor_ts, cursor_id),
            )

        # Normal ascending order for forward pagination
        query = query.order_by(asc(self.model.recorded_at), asc(self.model.id))

        # Limit + 1 to check for next page
        limit = params.limit or 50
        return query.limit(limit + 1).all(), total_count

    def get_total_count(self, db_session: DbSession) -> int:
        """Get total count of all data points."""
        return db_session.query(func.count(self.model.id)).scalar() or 0

    def get_count_in_range(self, db_session: DbSession, start_datetime: datetime, end_datetime: datetime) -> int:
        """Get count of data points within a datetime range."""
        return (
            db_session.query(func.count(self.model.id))
            .filter(self.model.recorded_at >= start_datetime)
            .filter(self.model.recorded_at < end_datetime)
            .scalar()
            or 0
        )

    def get_daily_histogram(self, db_session: DbSession, start_datetime: datetime, end_datetime: datetime) -> list[int]:
        """Get daily histogram of data points for the given date range.

        Returns a list of counts, one per day, ordered chronologically.
        """

        daily_counts = (
            db_session.query(cast(self.model.recorded_at, Date).label("date"), func.count(self.model.id).label("count"))
            .filter(self.model.recorded_at >= start_datetime)
            .filter(self.model.recorded_at < end_datetime)
            .group_by(cast(self.model.recorded_at, Date))
            .order_by(cast(self.model.recorded_at, Date))
            .all()
        )

        # Convert to list of counts, filling in zeros for missing days
        if not daily_counts:
            return []

        return [count for _, count in daily_counts]

    def get_count_by_series_type(self, db_session: DbSession) -> list[tuple[int, int]]:
        """Get count of data points grouped by series type ID.

        Returns list of (series_type_definition_id, count) tuples ordered by count descending.
        """
        results = (
            db_session.query(self.model.series_type_definition_id, func.count(self.model.id).label("count"))
            .group_by(self.model.series_type_definition_id)
            .order_by(func.count(self.model.id).desc())
            .all()
        )
        return [(series_type_definition_id, count) for series_type_definition_id, count in results]

    def get_count_by_source(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by source.

        Returns list of (source, count) tuples ordered by count descending.
        """
        results = (
            db_session.query(DataSource.source, func.count(self.model.id).label("count"))
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .group_by(DataSource.source)
            .order_by(func.count(self.model.id).desc())
            .all()
        )
        return [(source, count) for source, count in results]

    def get_averages_for_time_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, float | None]:
        """Get average values for specified series types within a time range.

        Uses half-open interval [start_time, end_time).

        Returns a dict mapping SeriesType to average value (or None if no data).
        """
        if not series_types:
            raise ValueError("series_types cannot be empty")

        type_ids = [get_series_type_id(t) for t in series_types]

        results = (
            db_session.query(
                self.model.series_type_definition_id,
                func.avg(self.model.value).label("avg_value"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_time,
                self.model.recorded_at < end_time,
                self.model.series_type_definition_id.in_(type_ids),
            )
            .group_by(self.model.series_type_definition_id)
            .all()
        )

        # Build result dict
        averages: dict[SeriesType, float | None] = {t: None for t in series_types}
        for type_id, avg_value in results:
            try:
                series_type = get_series_type_from_id(type_id)
                if series_type in averages:
                    averages[series_type] = float(avg_value) if avg_value is not None else None
            except KeyError:
                pass

        return averages

    def get_daily_activity_aggregates(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ActivityAggregateResult]:
        """Get daily activity aggregates from time-series data.

        Aggregates steps, energy, heart rate stats by date for a user.

        Returns list of dicts with keys:
        - activity_date, source, device_model
        - steps_sum, active_energy_sum, basal_energy_sum
        - hr_avg, hr_max, hr_min
        - distance_sum, flights_climbed_sum
        """
        # Series type IDs we need
        steps_id = get_series_type_id(SeriesType.steps)
        energy_id = get_series_type_id(SeriesType.energy)
        basal_energy_id = get_series_type_id(SeriesType.basal_energy)
        hr_id = get_series_type_id(SeriesType.heart_rate)
        distance_id = get_series_type_id(SeriesType.distance_walking_running)
        flights_id = get_series_type_id(SeriesType.flights_climbed)

        # Build aggregation query
        results = (
            db_session.query(
                cast(self.model.recorded_at, Date).label("activity_date"),
                DataSource.source.label("source"),
                DataSource.device_model.label("device_model"),
                # Steps - sum for the day
                func.sum(case((self.model.series_type_definition_id == steps_id, self.model.value), else_=0)).label(
                    "steps_sum"
                ),
                # Active energy - sum for the day
                func.sum(case((self.model.series_type_definition_id == energy_id, self.model.value), else_=0)).label(
                    "active_energy_sum"
                ),
                # Basal energy - sum for the day
                func.sum(
                    case((self.model.series_type_definition_id == basal_energy_id, self.model.value), else_=0)
                ).label("basal_energy_sum"),
                # Heart rate stats
                func.avg(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                    "hr_avg"
                ),
                func.max(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                    "hr_max"
                ),
                func.min(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                    "hr_min"
                ),
                # Distance - sum for the day (no else_=0 to return NULL when no data)
                func.sum(case((self.model.series_type_definition_id == distance_id, self.model.value))).label(
                    "distance_sum"
                ),
                # Flights climbed - sum for the day (no else_=0 to return NULL when no data)
                func.sum(case((self.model.series_type_definition_id == flights_id, self.model.value))).label(
                    "flights_climbed_sum"
                ),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_date,
                cast(self.model.recorded_at, Date) < cast(end_date, Date),
                self.model.series_type_definition_id.in_(
                    [steps_id, energy_id, basal_energy_id, hr_id, distance_id, flights_id]
                ),
            )
            .group_by(
                cast(self.model.recorded_at, Date),
                DataSource.source,
                DataSource.device_model,
            )
            .order_by(asc(cast(self.model.recorded_at, Date)))
            .all()
        )

        # Transform to list of dicts
        aggregates = []
        for row in results:
            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "steps_sum": int(row.steps_sum) if row.steps_sum else 0,
                    "active_energy_sum": float(row.active_energy_sum) if row.active_energy_sum else 0.0,
                    "basal_energy_sum": float(row.basal_energy_sum) if row.basal_energy_sum else 0.0,
                    "hr_avg": int(round(float(row.hr_avg))) if row.hr_avg is not None else None,
                    "hr_max": int(row.hr_max) if row.hr_max is not None else None,
                    "hr_min": int(row.hr_min) if row.hr_min is not None else None,
                    "distance_sum": float(row.distance_sum) if row.distance_sum is not None else None,
                    "flights_climbed_sum": int(row.flights_climbed_sum)
                    if row.flights_climbed_sum is not None
                    else None,
                }
            )
        return aggregates

    def get_daily_active_minutes(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        active_threshold: int = 30,
    ) -> list[ActiveMinutesResult]:
        """Get daily active/sedentary minutes from step data.

        Buckets step data by minute and counts:
        - active_minutes: minutes with steps >= threshold
        - tracked_minutes: total minutes with any step data
        - sedentary_minutes: tracked_minutes - active_minutes

        Args:
            active_threshold: Steps per minute to be considered "active" (default: 30)

        Returns list of dicts with keys:
        - activity_date, source, device_model
        - active_minutes, tracked_minutes, sedentary_minutes
        """
        steps_id = get_series_type_id(SeriesType.steps)

        # Create minute bucket expression using literal 'minute' text
        minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

        # Subquery: bucket step data by minute and sum steps per minute
        minute_bucket = (
            db_session.query(
                cast(self.model.recorded_at, Date).label("activity_date"),
                DataSource.source,
                DataSource.device_model,
                minute_trunc.label("minute_bucket"),
                func.sum(self.model.value).label("steps_in_minute"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_date,
                cast(self.model.recorded_at, Date) < cast(end_date, Date),
                self.model.series_type_definition_id == steps_id,
            )
            .group_by(
                cast(self.model.recorded_at, Date),
                DataSource.source,
                DataSource.device_model,
                minute_trunc,
            )
            .subquery()
        )

        # Main query: aggregate minute buckets to get daily active/tracked counts
        results = (
            db_session.query(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
                # Count minutes where steps >= threshold (active)
                func.sum(case((minute_bucket.c.steps_in_minute >= active_threshold, 1), else_=0)).label(
                    "active_minutes"
                ),
                # Count all tracked minutes
                func.count(minute_bucket.c.minute_bucket).label("tracked_minutes"),
            )
            .group_by(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
            )
            .order_by(asc(minute_bucket.c.activity_date))
            .all()
        )

        aggregates = []
        for row in results:
            active = int(row.active_minutes) if row.active_minutes else 0
            tracked = int(row.tracked_minutes) if row.tracked_minutes else 0
            sedentary = tracked - active

            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "active_minutes": active,
                    "tracked_minutes": tracked,
                    "sedentary_minutes": sedentary,
                }
            )
        return aggregates

    def get_daily_intensity_minutes(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        light_min: int,
        light_max: int,
        moderate_max: int,
        vigorous_max: int,
    ) -> list[IntensityMinutesResult]:
        """Get daily intensity minutes from heart rate data.

        Buckets HR data by minute and categorizes by intensity zone based on
        provided HR thresholds. Zone boundaries are calculated by the service layer.

        Args:
            light_min: Lower bound for light zone (inclusive)
            light_max: Upper bound for light zone (inclusive)
            moderate_max: Upper bound for moderate zone (inclusive, lower bound is light_max + 1)
            vigorous_max: Upper bound for vigorous zone (inclusive, lower bound is moderate_max + 1)

        Returns list of dicts with keys:
        - activity_date, source, device_model
        - light_minutes, moderate_minutes, vigorous_minutes
        """
        hr_id = get_series_type_id(SeriesType.heart_rate)

        # Create minute bucket expression
        minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

        # Subquery: bucket HR data by minute and get avg HR per minute
        minute_bucket = (
            db_session.query(
                cast(self.model.recorded_at, Date).label("activity_date"),
                DataSource.source,
                DataSource.device_model,
                minute_trunc.label("minute_bucket"),
                func.avg(self.model.value).label("avg_hr_in_minute"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_date,
                cast(self.model.recorded_at, Date) < cast(end_date, Date),
                self.model.series_type_definition_id == hr_id,
            )
            .group_by(
                cast(self.model.recorded_at, Date),
                DataSource.source,
                DataSource.device_model,
                minute_trunc,
            )
            .subquery()
        )

        # Main query: categorize minute buckets into intensity zones
        results = (
            db_session.query(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
                # Light: 50-63% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute >= light_min)
                            & (minute_bucket.c.avg_hr_in_minute <= light_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("light_minutes"),
                # Moderate: 64-76% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute > light_max)
                            & (minute_bucket.c.avg_hr_in_minute <= moderate_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("moderate_minutes"),
                # Vigorous: 77-93% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute > moderate_max)
                            & (minute_bucket.c.avg_hr_in_minute <= vigorous_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("vigorous_minutes"),
            )
            .group_by(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
            )
            .order_by(asc(minute_bucket.c.activity_date))
            .all()
        )

        aggregates = []
        for row in results:
            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "light_minutes": int(row.light_minutes) if row.light_minutes else 0,
                    "moderate_minutes": int(row.moderate_minutes) if row.moderate_minutes else 0,
                    "vigorous_minutes": int(row.vigorous_minutes) if row.vigorous_minutes else 0,
                }
            )
        return aggregates

    def get_latest_values_for_types(
        self,
        db_session: DbSession,
        user_id: UUID,
        before_date: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, tuple[float, datetime, str | None, str | None]]:
        """Get the most recent value for each series type before a given date.

        Used for slow-changing measurements like weight, height, body fat %.

        Args:
            before_date: Only consider measurements recorded before this datetime

        Returns:
            Dict mapping SeriesType to tuple of (value, recorded_at, source, device_model)
        """
        if not series_types:
            raise ValueError("series_types cannot be empty")

        type_ids = [get_series_type_id(t) for t in series_types]

        # Subquery to get the max recorded_at for each series type
        latest_subq = (
            db_session.query(
                self.model.series_type_definition_id,
                func.max(self.model.recorded_at).label("max_recorded_at"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at < before_date,
                self.model.series_type_definition_id.in_(type_ids),
            )
            .group_by(self.model.series_type_definition_id)
            .subquery()
        )

        # Main query to get the actual values at those timestamps
        # Use DISTINCT ON to handle multiple records with identical timestamps
        # Order by priorities to prefer higher priority sources
        results = (
            db_session.query(
                self.model.series_type_definition_id,
                self.model.value,
                self.model.recorded_at,
                DataSource.source,
                DataSource.device_model,
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .outerjoin(ProviderPriority, DataSource.provider == ProviderPriority.provider)
            .outerjoin(
                DeviceTypePriority,
                DataSource.device_type == cast(DeviceTypePriority.device_type, String),
            )
            .join(
                latest_subq,
                (self.model.series_type_definition_id == latest_subq.c.series_type_definition_id)
                & (self.model.recorded_at == latest_subq.c.max_recorded_at),
            )
            .filter(DataSource.user_id == user_id)
            # DISTINCT ON (PostgreSQL) ensures exactly one result per series type
            # Order by priorities (lower number = higher priority), then id desc as tiebreaker
            .distinct(self.model.series_type_definition_id)
            .order_by(
                self.model.series_type_definition_id,
                ProviderPriority.priority.asc().nulls_last(),
                DeviceTypePriority.priority.asc().nulls_last(),
                self.model.id.desc(),
            )
            .all()
        )

        # Build result dict
        latest_values: dict[SeriesType, tuple[float, datetime, str | None, str | None]] = {}
        for type_id, value, recorded_at, source, device_model in results:
            try:
                series_type = get_series_type_from_id(type_id)
                latest_values[series_type] = (float(value), recorded_at, source, device_model)
            except KeyError:
                pass

        return latest_values

    def get_aggregates_for_period(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, dict]:
        """Get aggregate statistics for each series type within a time period.

        Used for high-frequency measurements that need aggregation like
        resting heart rate, HRV, blood pressure.

        Returns:
            Dict mapping SeriesType to dict with keys: avg, min, max, count
        """
        if not series_types:
            raise ValueError("series_types cannot be empty")

        type_ids = [get_series_type_id(t) for t in series_types]

        results = (
            db_session.query(
                self.model.series_type_definition_id,
                func.avg(self.model.value).label("avg_value"),
                func.min(self.model.value).label("min_value"),
                func.max(self.model.value).label("max_value"),
                func.count(self.model.id).label("count"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_date,
                self.model.recorded_at < end_date,
                self.model.series_type_definition_id.in_(type_ids),
            )
            .group_by(self.model.series_type_definition_id)
            .all()
        )

        # Build result dict
        aggregates: dict[SeriesType, dict] = {}
        for type_id, avg_val, min_val, max_val, count in results:
            try:
                series_type = get_series_type_from_id(type_id)
                aggregates[series_type] = {
                    "avg": float(avg_val) if avg_val is not None else None,
                    "min": float(min_val) if min_val is not None else None,
                    "max": float(max_val) if max_val is not None else None,
                    "count": count,
                }
            except KeyError:
                pass

        return aggregates

    def get_latest_reading_within_window(
        self,
        db_session: DbSession,
        user_id: UUID,
        series_type: SeriesType,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[float, datetime, str, str | None] | None:
        """Get the most recent reading for a series type within a time window.

        Used for point-in-time metrics like body temperature that are only
        relevant if recently measured. Returns None if no reading exists
        within the specified window.

        Args:
            series_type: The type of measurement to retrieve
            window_start: Start of the valid time window
            window_end: End of the valid time window (typically now)

        Returns:
            Tuple of (value, recorded_at, provider_name, device_id) or None if no recent reading
        """
        type_id = get_series_type_id(series_type)

        result = (
            db_session.query(
                self.model.value,
                self.model.recorded_at,
                DataSource.source,
                DataSource.device_model,
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .outerjoin(ProviderPriority, DataSource.provider == ProviderPriority.provider)
            .outerjoin(
                DeviceTypePriority,
                DataSource.device_type == cast(DeviceTypePriority.device_type, String),
            )
            .filter(
                DataSource.user_id == user_id,
                self.model.series_type_definition_id == type_id,
                self.model.recorded_at >= window_start,
                self.model.recorded_at <= window_end,
            )
            .order_by(
                self.model.recorded_at.desc(),
                ProviderPriority.priority.asc().nulls_last(),
                DeviceTypePriority.priority.asc().nulls_last(),
            )
            .first()
        )

        if result is None:
            return None

        value, recorded_at, provider_name, device_id = result
        return (float(value), recorded_at, provider_name, device_id)
