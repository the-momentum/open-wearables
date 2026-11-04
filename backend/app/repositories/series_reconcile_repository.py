from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import NamedTuple
from uuid import UUID, uuid4

from sqlalchemy import Date, Interval, and_, delete, func, or_, select, text
from sqlalchemy import cast as sql_cast

from app.config import settings
from app.database import DbSession
from app.models import DataSource, SeriesAggregate
from app.repositories.aggregate_repository import AggregateRepository
from app.repositories.local_day import OFFSET_REACH, sample_day_sql, utc_midnight
from app.repositories.repositories import SourceRanking
from app.schemas.enums import (
    ComputedBy,
    PeriodKind,
    ProviderName,
    SeriesType,
    get_series_type_id,
)
from app.schemas.model_crud.activities import CalendarPeriod

# The user's own source the day values merged across their devices sit on (source_selection=reconcile): no device
# stands behind such a value. Every other read leaves it out.
RECONCILED_PROVIDER = ProviderName.INTERNAL
RECONCILED_SOURCE = "reconciled"
IS_RECONCILED_SOURCE = and_(DataSource.provider == RECONCILED_PROVIDER, DataSource.source == RECONCILED_SOURCE)
# Not its negation: an internal source without a source name must not drop out with NOT (... AND NULL).
NOT_RECONCILED_SOURCE = or_(
    DataSource.provider != RECONCILED_PROVIDER, DataSource.source.is_distinct_from(RECONCILED_SOURCE)
)

# The local day of a series_aggregate row: its UTC start moved by its offset.
_ROW_DAY = sql_cast(
    func.timezone("UTC", SeriesAggregate.period_start) + sql_cast(SeriesAggregate.zone_offset, Interval), Date
)

# The series reconcile merges: amounts that accumulate over time, where two devices recording the same moment
# recorded the same thing, so that moment counts once. Every other series reads as per_period.
RECONCILED_SERIES: frozenset[SeriesType] = frozenset(
    {
        # Movement: devices double-count the same walk, ride or swim.
        SeriesType.steps,
        SeriesType.distance,
        SeriesType.distance_walking_running,
        SeriesType.distance_cycling,
        SeriesType.distance_swimming,
        SeriesType.distance_downhill_snow_sports,
        SeriesType.distance_other,
        SeriesType.active_energy,
        SeriesType.flights_climbed,
        SeriesType.elevation_gain,
        SeriesType.swimming_stroke_count,
        SeriesType.push_count,
        # Minutes of activity: a minute two devices counted is one minute.
        SeriesType.active_time,
        SeriesType.exercise_time,
    }
)

# What the SQL filters on.
_RECONCILED_TYPE_IDS = sorted(get_series_type_id(series_type) for series_type in RECONCILED_SERIES)
# The span given to a sample without a window, so an instant can still be covered.
INSTANT_SECONDS = 60


def _mergeable(alias: str) -> str:
    """Samples that cover part of a day: a day's own total or a whole-day window has no time to split."""
    return f"{alias}.is_daily_total IS NOT TRUE AND coalesce({alias}.window_seconds, 0) < 86400"


def _length(alias: str) -> str:
    return f"coalesce({alias}.window_seconds, {INSTANT_SECONDS})"


# One index probe per source: which of the user's sources hold a summed sample in the range at all.
_SOURCES_WITH_SAMPLES = text(f"""
    SELECT src.id
    FROM unnest(CAST(:source_ids AS uuid[])) AS src(id)
    CROSS JOIN LATERAL (
        SELECT 1 FROM series_sample s
        WHERE s.data_source_id = src.id AND s.series_type_definition_id = ANY(:type_ids)
            AND s.recorded_at >= :lo AND s.recorded_at < :hi AND {_mergeable("s")}
        ORDER BY s.recorded_at LIMIT 1
    ) probe
""")

# Each sample counts for the share of its window the union of better-ranked windows (widened by :tolerance, as two
# apps reading one sensor start their windows seconds apart) leaves uncovered; only days two sources fed come back.
_MERGE = text(f"""
    WITH src(id, pos) AS (SELECT * FROM unnest(CAST(:source_ids AS uuid[]), CAST(:positions AS integer[]))),
    widest AS MATERIALIZED (
        SELECT s.data_source_id, s.series_type_definition_id, max({_length("s")}) AS seconds
        FROM series_sample s
        WHERE s.data_source_id = ANY(CAST(:source_ids AS uuid[])) AND s.series_type_definition_id = ANY(:type_ids)
            AND s.recorded_at >= CAST(:lo AS timestamptz) - interval '1 day' AND s.recorded_at < :hi
            AND {_mergeable("s")}
        GROUP BY 1, 2
    )
    SELECT x.series_type_definition_id AS type_id, {sample_day_sql("x")} AS day,
        sum(x.value * (1 - least(coalesce(c.covered, 0), w.seconds) / w.seconds)) AS sum,
        count(*) FILTER (WHERE coalesce(c.covered, 0) < w.seconds) AS count,
        (array_agg(coalesce(x.zone_offset, '+00:00') ORDER BY x.recorded_at))[1] AS zone_offset
    FROM series_sample x
    JOIN src ON src.id = x.data_source_id
    CROSS JOIN LATERAL (SELECT {_length("x")}::numeric AS seconds) w
    LEFT JOIN LATERAL (
        SELECT sum(extract(epoch FROM upper(part) - lower(part))) AS covered
        FROM (
            SELECT range_agg(tstzrange(
                b.recorded_at - :tolerance * interval '1 second',
                b.recorded_at + ({_length("b")} + :tolerance) * interval '1 second'
            )) AS better_windows
            FROM src better
            JOIN widest ON widest.data_source_id = better.id
                AND widest.series_type_definition_id = x.series_type_definition_id
            JOIN series_sample b ON b.data_source_id = better.id
                AND b.series_type_definition_id = x.series_type_definition_id
                AND b.recorded_at < x.recorded_at + (w.seconds + :tolerance) * interval '1 second'
                AND b.recorded_at > x.recorded_at - (widest.seconds + :tolerance) * interval '1 second'
                AND b.recorded_at + ({_length("b")} + :tolerance) * interval '1 second' > x.recorded_at
            WHERE better.pos < src.pos AND {_mergeable("b")}
        ) better
        CROSS JOIN LATERAL unnest(
            better.better_windows
            * tstzmultirange(tstzrange(x.recorded_at, x.recorded_at + w.seconds * interval '1 second'))
        ) AS part
    ) c ON true
    WHERE x.data_source_id = ANY(CAST(:source_ids AS uuid[])) AND x.series_type_definition_id = ANY(:type_ids)
        AND x.recorded_at >= :lo AND x.recorded_at < :hi AND {_mergeable("x")} AND {sample_day_sql("x")} = ANY(:days)
    GROUP BY 1, 2
    HAVING count(DISTINCT x.data_source_id) > 1
""")

# Every reconciled row of the days, so a day one source dropped out of does not keep a merge of two.
_DELETE_DAYS = text("""
    DELETE FROM series_aggregate a
    WHERE a.data_source_id = :source_id AND a.period_kind = :period_kind
        AND a.period_start >= :lo AND a.period_start < :hi
        AND ((a.period_start AT TIME ZONE 'UTC') + a.zone_offset::interval)::date = ANY(:days)
""")


class MergedDay(NamedTuple):
    """A merged series' total on one local day."""

    type_id: int
    day: date
    zone_offset: str
    sum: float
    count: int


class SeriesReconcileRepository:
    """Merges a user's sources' RECONCILED_SERIES per local day into rows on the user's reconciled source: each moment
    counted once, from the best-ranked source that recorded it, as a phone's steps fill the hours a watch was off.

    Only days two sources hold samples on get a row; reads fall back to the best source's own day elsewhere.
    """

    def __init__(self) -> None:
        self.series_aggregate_repo = AggregateRepository(SeriesAggregate)

    def reconcile(
        self,
        db_session: DbSession,
        user_id: UUID,
        days: Iterable[date],
        ranking: SourceRanking,
        keep_existing: bool = False,
    ) -> int:
        """Recompute the reconciled rows of ``days`` from the samples stored now; returns the rows written.

        ``keep_existing`` only adds missing rows: retention deletes a day's samples a source at a time, and once one
        source's are gone the day can no longer be merged, only kept.
        """
        days = sorted(set(days))
        if not days:
            return 0
        reconciled = self.reconciled_source(db_session, user_id)
        if reconciled is not None and not keep_existing:
            lo, hi = _bounds(days)
            db_session.execute(
                _DELETE_DAYS,
                {"source_id": reconciled.id, "period_kind": PeriodKind.DAY, "lo": lo, "hi": hi, "days": days},
            )
        merged = self.merge(db_session, user_id, days, ranking)
        if not merged:
            return 0
        reconciled = reconciled or self._create_reconciled_source(db_session, user_id)
        rows = []
        for day in merged:
            period = CalendarPeriod.of_date(day.day, day.zone_offset)
            rows.append(
                {
                    "data_source_id": reconciled.id,
                    "series_type_definition_id": day.type_id,
                    "period_kind": PeriodKind.DAY,
                    "period_start": period.start,
                    "period_end": period.end,
                    "zone_offset": period.zone_offset,
                    "computed_by": ComputedBy.OPEN_WEARABLES,
                    "sum": round(day.sum, 3),
                    "count": day.count,
                }
            )
        if keep_existing:
            # Later sources of a retention pass merge without the ones already deleted: never over a full merge.
            return self.series_aggregate_repo.insert_missing(db_session, rows)
        return self.series_aggregate_repo.upsert(db_session, rows)

    def merge(
        self,
        db_session: DbSession,
        user_id: UUID,
        days: Iterable[date],
        ranking: SourceRanking,
        type_ids: list[int] | None = None,
    ) -> list[MergedDay]:
        """Each merged series' total on each of ``days`` two of the user's sources hold samples on, unless a source
        ranked above all of them holds only its own day value there: that day stays the best source's, as per_period.
        """
        days = sorted(set(days))
        if not days:
            return []
        lo, hi = _bounds(days)
        params = {"lo": lo, "hi": hi, "days": days, "type_ids": type_ids or _RECONCILED_TYPE_IDS}
        sources = db_session.query(DataSource).filter(DataSource.user_id == user_id, ~IS_RECONCILED_SOURCE).all()
        with_samples = self.sources_with_samples(db_session, [s.id for s in sources], days, params["type_ids"])
        if len(with_samples) < 2:
            return []
        ordered = sorted(
            (source for source in sources if source.id in with_samples),
            key=lambda source: (*ranking.rank(source.provider, source.device_type), str(source.id)),
        )
        best = ranking.rank(ordered[0].provider, ordered[0].device_type)
        above = [s.id for s in sources if s.id not in with_samples and ranking.rank(s.provider, s.device_type) < best]
        day_only = self._held_days(db_session, above, params["type_ids"], days) if above else set()
        # The planner overestimates the merge and JIT-compiles it, which costs more than running it.
        db_session.execute(text("SET LOCAL jit = off"))
        rows = db_session.execute(
            _MERGE,
            {
                **params,
                "source_ids": [s.id for s in ordered],
                "positions": list(range(len(ordered))),
                "tolerance": settings.reconcile_edge_tolerance_seconds,
            },
        )
        return [
            MergedDay(row.type_id, row.day, row.zone_offset, float(row.sum), row.count)
            for row in rows
            if (row.type_id, row.day) not in day_only
        ]

    @staticmethod
    def sources_with_samples(
        db_session: DbSession, source_ids: list[UUID], days: list[date], type_ids: list[int] | None = None
    ) -> set[UUID]:
        """Which of the sources hold a mergeable sample of the series in the local days' range."""
        if not source_ids or not days:
            return set()
        lo, hi = _bounds(sorted(days))
        params = {"lo": lo, "hi": hi, "type_ids": type_ids or _RECONCILED_TYPE_IDS, "source_ids": source_ids}
        return set(db_session.execute(_SOURCES_WITH_SAMPLES, params).scalars())

    @staticmethod
    def _held_days(
        db_session: DbSession, source_ids: list[UUID], type_ids: list[int], days: list[date]
    ) -> set[tuple[int, date]]:
        lo, hi = _bounds(days)
        rows = db_session.query(SeriesAggregate.series_type_definition_id, _ROW_DAY).filter(
            SeriesAggregate.data_source_id.in_(source_ids),
            SeriesAggregate.series_type_definition_id.in_(type_ids),
            SeriesAggregate.period_kind == PeriodKind.DAY,
            SeriesAggregate.period_start >= lo,
            SeriesAggregate.period_start < hi,
            _ROW_DAY.in_(days),
        )
        return {(type_id, day) for type_id, day in rows.distinct()}

    @staticmethod
    def delete_reconciled_rows(db_session: DbSession, since: date | None, batch: int) -> int:
        """Delete up to ``batch`` stored merged rows from ``since`` on (every one when None); returns how many."""
        reconciled = select(DataSource.id).where(IS_RECONCILED_SOURCE).scalar_subquery()
        chosen = select(SeriesAggregate.id).where(SeriesAggregate.data_source_id.in_(reconciled))
        if since is not None:
            chosen = chosen.where(SeriesAggregate.period_start >= utc_midnight(since) - OFFSET_REACH)
        stmt = delete(SeriesAggregate).where(SeriesAggregate.id.in_(chosen.limit(batch)))
        result = db_session.execute(stmt.execution_options(synchronize_session=False))
        return result.rowcount  # ty: ignore[unresolved-attribute]

    @staticmethod
    def day_rows(
        db_session: DbSession, source_id: UUID, type_ids: list[int], first_day: date, last_day: date
    ) -> dict[tuple[int, date], SeriesAggregate]:
        """The stored merged rows of the local days from ``first_day`` to ``last_day``, by (series type, day)."""
        lo, hi = _bounds([first_day, last_day])
        rows = (
            db_session.query(SeriesAggregate, _ROW_DAY)
            .filter(
                SeriesAggregate.data_source_id == source_id,
                SeriesAggregate.series_type_definition_id.in_(type_ids),
                SeriesAggregate.period_kind == PeriodKind.DAY,
                SeriesAggregate.period_start >= lo,
                SeriesAggregate.period_start < hi,
                _ROW_DAY.between(first_day, last_day),
            )
            .all()
        )
        return {(row.series_type_definition_id, day): row for row, day in rows}

    @staticmethod
    def reconciled_source(db_session: DbSession, user_id: UUID) -> DataSource | None:
        return db_session.query(DataSource).filter(DataSource.user_id == user_id, IS_RECONCILED_SOURCE).first()

    @staticmethod
    def _create_reconciled_source(db_session: DbSession, user_id: UUID) -> DataSource:
        source = DataSource(id=uuid4(), user_id=user_id, provider=RECONCILED_PROVIDER, source=RECONCILED_SOURCE)
        db_session.add(source)
        db_session.flush()
        return source


def _bounds(days: list[date]) -> tuple[datetime, datetime]:
    """The UTC range holding every sample of the local days, whatever their offsets."""
    return utc_midnight(days[0]) - OFFSET_REACH, utc_midnight(days[-1]) + timedelta(days=1) + OFFSET_REACH


def is_reconciled(source: DataSource) -> bool:
    return source.provider == RECONCILED_PROVIDER and source.source == RECONCILED_SOURCE
