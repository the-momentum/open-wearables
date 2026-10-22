from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import Date, Interval, cast, func, tuple_
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import DataSource, SeriesAggregate
from app.repositories.repositories import source_filter_conditions
from app.schemas.enums import ComputedBy, PeriodKind, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import TimeSeriesQueryParams

# A local day starts up to 14 hours either side of its UTC midnight.
_OFFSET_REACH = timedelta(hours=14)

LOCAL_DAY = cast(
    func.timezone("UTC", SeriesAggregate.period_start) + cast(SeriesAggregate.zone_offset, Interval), Date
).label("day")


class SeriesAggregateRepository:
    """Reads day rows of series_aggregate: one per data source, series and local day, the provider's before ours."""

    def get_day_rows(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        first_day: date,
        last_day: date,
        source_by_type: dict[int, UUID] | None = None,
    ) -> list[tuple[SeriesAggregate, date]]:
        """Day rows from ``first_day`` to ``last_day`` inclusive, ordered by day."""
        rows = (
            self._days(db_session, user_id, params, types, first_day, last_day, source_by_type)
            .add_columns(LOCAL_DAY)
            .distinct(SeriesAggregate.data_source_id, SeriesAggregate.series_type_definition_id, LOCAL_DAY)
            .order_by(
                SeriesAggregate.data_source_id,
                SeriesAggregate.series_type_definition_id,
                LOCAL_DAY,
                (SeriesAggregate.computed_by == ComputedBy.PROVIDER).desc(),
            )
            .all()
        )
        return sorted(((row, day) for row, day in rows), key=lambda pair: pair[1])

    def edge_day(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        first_day: date,
        last_day: date,
        source_by_type: dict[int, UUID] | None = None,
        latest: bool = False,
    ) -> date | None:
        """The earliest (or latest) local day in the range that holds a row, None if none does."""
        query = self._days(db_session, user_id, params, types, first_day, last_day, source_by_type)
        return query.with_entities(func.max(LOCAL_DAY) if latest else func.min(LOCAL_DAY)).scalar()

    @staticmethod
    def _days(
        db_session: DbSession,
        user_id: UUID,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        first_day: date,
        last_day: date,
        source_by_type: dict[int, UUID] | None,
    ) -> Query:
        query = (
            db_session.query(SeriesAggregate)
            .join(DataSource, SeriesAggregate.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                SeriesAggregate.period_kind == PeriodKind.DAY,
                # The bounds keep the index in play; the local day decides.
                SeriesAggregate.period_start >= _utc_midnight(first_day) - _OFFSET_REACH,
                SeriesAggregate.period_start < _utc_midnight(last_day) + timedelta(days=1) + _OFFSET_REACH,
                first_day <= LOCAL_DAY,
                last_day >= LOCAL_DAY,
                *source_filter_conditions(params, SeriesAggregate.data_source_id),
            )
        )
        if types:
            query = query.filter(SeriesAggregate.series_type_definition_id.in_([get_series_type_id(t) for t in types]))
        if source_by_type is not None:
            query = query.filter(
                tuple_(SeriesAggregate.series_type_definition_id, SeriesAggregate.data_source_id).in_(
                    list(source_by_type.items())
                )
            )
        return query


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time(), timezone.utc)
