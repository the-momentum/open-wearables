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
from app.schemas.series_types import SeriesType, get_series_type_id
from app.utils.dates import parse_query_datetime
from app.utils.exceptions import InvalidCursorError


class DataPointSeriesRepository(
    CrudRepository[DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Repository for unified device data point series."""

    def __init__(self, model: type[DataPointSeries]):
        super().__init__(model)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)

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
        series_type: SeriesType,
        user_id: UUID,
    ) -> list[tuple[DataPointSeries, ExternalDeviceMapping]]:
        query = (
            db_session.query(self.model, ExternalDeviceMapping)
            .join(
                ExternalDeviceMapping,
                self.model.external_device_mapping_id == ExternalDeviceMapping.id,
            )
            .filter(self.model.series_type_definition_id == get_series_type_id(series_type))
            .filter(ExternalDeviceMapping.user_id == user_id)
        )

        if params.external_device_mapping_id:
            query = query.filter(self.model.external_device_mapping_id == params.external_device_mapping_id)
        elif params.device_id:
            query = query.filter(ExternalDeviceMapping.device_id == params.device_id)

        if getattr(params, "provider_name", None):
            query = query.filter(ExternalDeviceMapping.provider_name == params.provider_name)

        if params.start_datetime:
            query = query.filter(self.model.recorded_at >= params.start_datetime)

        if params.end_datetime:
            query = query.filter(self.model.recorded_at <= params.end_datetime)

        # Cursor pagination (keyset)
        if params.cursor:
            # Expected cursor format: "timestamp_iso|id"
            try:
                cursor_ts_str, cursor_id_str = params.cursor.split("|")
                cursor_ts = parse_query_datetime(cursor_ts_str)
                cursor_id = UUID(cursor_id_str)
            except (ValueError, TypeError):
                raise InvalidCursorError(cursor=params.cursor)

            # WHERE (recorded_at, id) > (cursor_ts, cursor_id)
            # Since we order by recorded_at ASC, id ASC
            query = query.filter(
                tuple_(self.model.recorded_at, self.model.id) > (cursor_ts, cursor_id),
            )

        query = query.order_by(asc(self.model.recorded_at), asc(self.model.id))

        # Limit + 1 to check for next page
        limit = params.limit or 50
        return query.limit(limit + 1).all()

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
