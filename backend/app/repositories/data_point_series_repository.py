from datetime import datetime
from uuid import UUID

from sqlalchemy import Date, asc, cast, func, tuple_

from app.database import DbSession
from app.models import DataPointSeries, ExternalDeviceMapping
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.repositories.repositories import CrudRepository
from app.schemas import (
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.series_types import SeriesType, get_series_type_from_id, get_series_type_id
from app.utils.duplicates import handle_duplicates
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import decode_cursor


class DataPointSeriesRepository(
    CrudRepository[DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Repository for unified device data point series."""

    def __init__(self, model: type[DataPointSeries]):
        super().__init__(model)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)

    @handle_exceptions
    @handle_duplicates
    def create(self, db_session: DbSession, creator: TimeSeriesSampleCreate) -> DataPointSeries:
        mapping = self.mapping_repo.ensure_mapping(
            db_session,
            creator.user_id,
            creator.provider_name,
            creator.device_id,
            creator.external_device_mapping_id,
        )

        creation_data = creator.model_dump()
        creation_data["external_device_mapping_id"] = mapping.id
        creation_data["series_type_definition_id"] = get_series_type_id(creator.series_type)
        for redundant_key in ("user_id", "provider_name", "device_id", "series_type"):
            creation_data.pop(redundant_key, None)

        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def get_samples(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
    ) -> tuple[list[tuple[DataPointSeries, ExternalDeviceMapping]], int]:
        """Get data points with filtering and keyset pagination.

        Returns a tuple of (samples, total_count) where total_count is calculated
        BEFORE applying cursor pagination, giving the total number of matching records.
        """
        query = (
            db_session.query(self.model, ExternalDeviceMapping)
            .join(
                ExternalDeviceMapping,
                self.model.external_device_mapping_id == ExternalDeviceMapping.id,
            )
            .filter(ExternalDeviceMapping.user_id == user_id)
        )

        if types:
            type_ids = [get_series_type_id(t) for t in types]
            query = query.filter(self.model.series_type_definition_id.in_(type_ids))

        if params.device_id:
            query = query.filter(ExternalDeviceMapping.device_id == params.device_id)

        if getattr(params, "provider_name", None):
            query = query.filter(ExternalDeviceMapping.provider_name == params.provider_name)

        if params.start_datetime:
            query = query.filter(self.model.recorded_at >= params.start_datetime)

        if params.end_datetime:
            query = query.filter(self.model.recorded_at <= params.end_datetime)

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

    def get_count_by_provider(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by provider.

        Returns list of (provider_name, count) tuples ordered by count descending.
        """
        results = (
            db_session.query(ExternalDeviceMapping.provider_name, func.count(self.model.id).label("count"))
            .join(ExternalDeviceMapping, self.model.external_device_mapping_id == ExternalDeviceMapping.id)
            .group_by(ExternalDeviceMapping.provider_name)
            .order_by(func.count(self.model.id).desc())
            .all()
        )
        return [(provider_name, count) for provider_name, count in results]

    def get_averages_for_time_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, float | None]:
        """Get average values for specified series types within a time range.

        Returns a dict mapping SeriesType to average value (or None if no data).
        """
        if not series_types:
            return {}

        type_ids = [get_series_type_id(t) for t in series_types]

        results = (
            db_session.query(
                self.model.series_type_definition_id,
                func.avg(self.model.value).label("avg_value"),
            )
            .join(ExternalDeviceMapping, self.model.external_device_mapping_id == ExternalDeviceMapping.id)
            .filter(
                ExternalDeviceMapping.user_id == user_id,
                self.model.recorded_at >= start_time,
                self.model.recorded_at <= end_time,
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
