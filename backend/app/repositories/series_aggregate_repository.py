from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import Date, Interval, func, text, tuple_
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import DataSource, SeriesAggregate
from app.repositories.local_day import OFFSET_REACH, utc_midnight
from app.repositories.repositories import source_filter_conditions
from app.schemas.enums import ComputedBy, PeriodKind, SeriesType, get_series_type_from_id, get_series_type_id
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.model_crud.activities import TimeSeriesQueryParams
from app.schemas.responses.activity import ActivityAggregateResult

LOCAL_DAY = sql_cast(
    func.timezone("UTC", SeriesAggregate.period_start) + sql_cast(SeriesAggregate.zone_offset, Interval), Date
).label("day")

_ALL_TYPE_IDS = [get_series_type_id(series_type) for series_type in SeriesType]

# Per (series, source) pair, the first (or last) day row in the range: one index probe per pair, ordered on the
# index's period_start, where a MIN over a join filtered by the local day reads every row of the range.
_EDGE_ROWS = {
    latest: text(f"""
        SELECT c.type_id, c.source_id, edge.period_start
        FROM unnest(CAST(:type_ids AS integer[]), CAST(:source_ids AS uuid[])) AS c(type_id, source_id)
        CROSS JOIN LATERAL (
            SELECT a.period_start FROM series_aggregate a
            WHERE a.data_source_id = c.source_id AND a.series_type_definition_id = c.type_id
                AND a.period_kind = 'day' AND a.period_start >= :lo AND a.period_start < :hi
                AND ((a.period_start AT TIME ZONE 'UTC') + a.zone_offset::interval)::date
                    BETWEEN :first_day AND :last_day
            ORDER BY a.period_start {"DESC" if latest else "ASC"} LIMIT 1
        ) edge
    """)
    for latest in (False, True)
}


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
                # Two provider rows can land on one local day (a Whoop cycle starting 23:30, the next at 01:00
                # the same date); the later one is the one the provider wrote last.
                SeriesAggregate.period_start.desc(),
            )
            .all()
        )
        return sorted(((row, day) for row, day in rows), key=lambda pair: pair[1])

    def edge_rows(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        first_day: date,
        last_day: date,
        source_by_type: dict[int, UUID] | None = None,
        latest: bool = False,
    ) -> dict[tuple[int, UUID], datetime]:
        """Every (series, data source) pair with a day row in the range, and its first (or last) row's start."""
        if source_by_type is not None:
            pairs = list(source_by_type.items())
        else:
            sources = (
                db_session.query(DataSource.id)
                .filter(DataSource.user_id == user_id, *source_filter_conditions(params, DataSource.id))
                .all()
            )
            type_ids = [get_series_type_id(t) for t in types] if types else _ALL_TYPE_IDS
            pairs = [(type_id, source_id) for type_id in type_ids for (source_id,) in sources]
        if not pairs:
            return {}
        rows = db_session.execute(
            _EDGE_ROWS[latest],
            {
                "type_ids": [type_id for type_id, _ in pairs],
                "source_ids": [source_id for _, source_id in pairs],
                "lo": utc_midnight(first_day) - OFFSET_REACH,
                "hi": utc_midnight(last_day) + timedelta(days=1) + OFFSET_REACH,
                "first_day": first_day,
                "last_day": last_day,
            },
        )
        return {(row.type_id, row.source_id): row.period_start for row in rows}

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
        edge_starts: Iterable[datetime] | None = None,
    ) -> date | None:
        """The earliest (or latest) local day in the range that holds a row, None if none does."""
        if edge_starts is None:
            edge_starts = self.edge_rows(
                db_session, user_id, params, types, first_day, last_day, source_by_type, latest
            ).values()
        if not (starts := list(edge_starts)):
            return None
        edge_start = max(starts) if latest else min(starts)
        # The edge day lies among the rows within a day of the edge instant: an offset moves a day by at most that.
        start = SeriesAggregate.period_start
        near = self._days(db_session, user_id, params, types, first_day, last_day, source_by_type).filter(
            start >= edge_start - 2 * OFFSET_REACH, start <= edge_start + 2 * OFFSET_REACH
        )
        return near.with_entities(func.max(LOCAL_DAY) if latest else func.min(LOCAL_DAY)).scalar()

    def period_averages(
        self, db_session: DbSession, user_id: UUID, types: list[SeriesType], first_day: date, last_day: date
    ) -> dict[SeriesType, float]:
        """Each series' mean of its day values from ``first_day`` to ``last_day`` inclusive: one value per
        data source and local day, the provider's before ours, read from the column the series is read by."""
        found: dict[SeriesType, list[float]] = defaultdict(list)
        for row, _ in self.get_day_rows(db_session, user_id, TimeSeriesQueryParams(), types, first_day, last_day):
            series_type = get_series_type_from_id(row.series_type_definition_id)
            if (value := day_value(row, series_type)) is not None:
                found[series_type].append(value)
        return {series_type: sum(values) / len(values) for series_type, values in found.items()}

    def latest_day_value(
        self, db_session: DbSession, user_id: UUID, series_type: SeriesType, since: date
    ) -> tuple[float, datetime] | None:
        """The newest day value of the series on or after ``since``, with the instant its day starts."""
        last_day = date.today() + timedelta(days=1)
        rows = self.get_day_rows(db_session, user_id, TimeSeriesQueryParams(), [series_type], since, last_day)
        for row, _ in reversed(rows):
            if (value := day_value(row, series_type)) is not None:
                return value, row.period_start
        return None

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
                SeriesAggregate.period_start >= utc_midnight(first_day) - OFFSET_REACH,
                SeriesAggregate.period_start < utc_midnight(last_day) + timedelta(days=1) + OFFSET_REACH,
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


def day_value(row: SeriesAggregate, series_type: SeriesType) -> float | None:
    """The one number a day row stands for: the statistic its series is read by, else the day's last value."""
    value = getattr(row, get_aggregation_method(series_type).value)
    if value is None:
        value = row.last
    return float(value) if value is not None else None


# The day sums and heart rate an activity summary shows, by the key its rows carry.
_ACTIVITY_SUMS = {
    SeriesType.steps: "steps_sum",
    SeriesType.active_energy: "active_energy_sum",
    SeriesType.basal_energy: "basal_energy_sum",
    SeriesType.total_energy: "total_energy_sum",
    SeriesType.distance_walking_running: "distance_sum",
    SeriesType.flights_climbed: "flights_climbed_sum",
    SeriesType.active_time: "active_time_minutes",
}
_INT_SUMS = {"steps_sum", "flights_climbed_sum", "active_time_minutes"}


def daily_activity(
    db_session: DbSession, user_id: UUID, start: datetime, end: datetime
) -> list[ActivityAggregateResult]:
    """One row per local day and device in [start, end), from the day rows (the provider's, else ours).

    Data sources that share provider, source, device model and type add up, as their samples did.
    """
    types = [*_ACTIVITY_SUMS, SeriesType.heart_rate]
    rows = SeriesAggregateRepository().get_day_rows(
        db_session, user_id, TimeSeriesQueryParams(), types, start.date(), (end - timedelta(microseconds=1)).date()
    )
    sources = {
        s.id: s for s in db_session.query(DataSource).filter(DataSource.id.in_({r.data_source_id for r, _ in rows}))
    }
    days: dict[tuple, list[SeriesAggregate]] = {}
    for row, day in rows:
        source = sources[row.data_source_id]
        days.setdefault((day, source.provider, source.source, source.device_model, source.device_type), []).append(row)

    heart_rate_id = get_series_type_id(SeriesType.heart_rate)
    sum_keys = {get_series_type_id(series_type): key for series_type, key in _ACTIVITY_SUMS.items()}
    results: list[ActivityAggregateResult] = []
    for (day, provider, source, device_model, device_type), day_rows in days.items():
        result: dict = {
            "activity_date": day,
            "provider": provider,
            "source": source,
            "device_model": device_model,
            "device_type": device_type,
            **dict.fromkeys(_ACTIVITY_SUMS.values()),
            "hr_avg": None,
            "hr_max": None,
            "hr_min": None,
        }
        for type_id, key in sum_keys.items():
            sums = [float(r.sum) for r in day_rows if r.series_type_definition_id == type_id and r.sum is not None]
            if sums:
                result[key] = round(sum(sums)) if key in _INT_SUMS else sum(sums)
        heart_rate = [r for r in day_rows if r.series_type_definition_id == heart_rate_id]
        weighted = [(float(r.avg), r.count) for r in heart_rate if r.avg is not None]
        if weighted:
            result["hr_avg"] = round(sum(a * c for a, c in weighted) / sum(c for _, c in weighted))
        if maxes := [int(r.max) for r in heart_rate if r.max is not None]:
            result["hr_max"] = max(maxes)
        if mins := [int(r.min) for r in heart_rate if r.min is not None]:
            result["hr_min"] = min(mins)
        results.append(cast(ActivityAggregateResult, result))
    return sorted(results, key=lambda r: r["activity_date"])
