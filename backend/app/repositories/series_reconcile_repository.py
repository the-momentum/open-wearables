from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import NamedTuple
from uuid import UUID, uuid4

from sqlalchemy import and_, text

from app.database import DbSession
from app.models import DataSource, SeriesAggregate
from app.repositories.aggregate_repository import AggregateRepository
from app.repositories.local_day import OFFSET_REACH, sample_day_sql, utc_midnight
from app.repositories.repositories import SourceRanking
from app.schemas.enums import (
    AGGREGATION_METHOD_BY_TYPE,
    AggregationMethod,
    ComputedBy,
    PeriodKind,
    ProviderName,
    get_series_type_id,
)
from app.schemas.model_crud.activities import CalendarPeriod

# The user's own source the reconciled day rows sit on: no device stands behind a value merged from several.
RECONCILED_PROVIDER = ProviderName.INTERNAL
RECONCILED_SOURCE = "reconciled"
IS_RECONCILED_SOURCE = and_(DataSource.provider == RECONCILED_PROVIDER, DataSource.source == RECONCILED_SOURCE)

# Summed series only: a step or a kilocalorie spread over a window can be split by time, a heart rate cannot.
RECONCILED_TYPE_IDS = sorted(
    get_series_type_id(series_type)
    for series_type, method in AGGREGATION_METHOD_BY_TYPE.items()
    if method is AggregationMethod.SUM
)
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

# Each sample counts for the share of its window no better-ranked source covers. Exact for two sources whose own
# samples do not overlap; where three or more overlap, better sources' overlaps can add up past their union and are
# capped at the window. Only (series, day) pairs two sources contributed to are returned.
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
        SELECT sum(extract(epoch FROM
                least(x.recorded_at + w.seconds * interval '1 second',
                      b.recorded_at + {_length("b")} * interval '1 second')
                - greatest(x.recorded_at, b.recorded_at))) AS covered
        FROM src better
        JOIN widest ON widest.data_source_id = better.id
            AND widest.series_type_definition_id = x.series_type_definition_id
        JOIN series_sample b ON b.data_source_id = better.id
            AND b.series_type_definition_id = x.series_type_definition_id
            AND b.recorded_at < x.recorded_at + w.seconds * interval '1 second'
            AND b.recorded_at > x.recorded_at - widest.seconds * interval '1 second'
            AND b.recorded_at + {_length("b")} * interval '1 second' > x.recorded_at
        WHERE better.pos < src.pos AND {_mergeable("b")}
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
    """A summed series' merged total on one local day."""

    type_id: int
    day: date
    zone_offset: str
    sum: float
    count: int


class SeriesReconcileRepository:
    """Merges a user's sources' summed series per local day into rows on the user's reconciled source: each moment
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

        ``keep_existing`` only adds or refreshes rows, never removes one: retention deletes a day's samples a source
        at a time, and once one source's are gone the day can no longer be merged, only kept.
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
        return self.series_aggregate_repo.upsert(db_session, rows)

    def merge(
        self, db_session: DbSession, user_id: UUID, days: Iterable[date], ranking: SourceRanking
    ) -> list[MergedDay]:
        """Each summed series' merged total on each of ``days`` two of the user's sources hold samples on."""
        days = sorted(set(days))
        if not days:
            return []
        lo, hi = _bounds(days)
        params = {"lo": lo, "hi": hi, "days": days, "type_ids": RECONCILED_TYPE_IDS}
        sources = db_session.query(DataSource).filter(DataSource.user_id == user_id, ~IS_RECONCILED_SOURCE).all()
        with_samples = set(
            db_session.execute(_SOURCES_WITH_SAMPLES, {**params, "source_ids": [s.id for s in sources]}).scalars()
        )
        if len(with_samples) < 2:
            return []
        ordered = sorted(
            (source for source in sources if source.id in with_samples),
            key=lambda source: (*ranking.rank(source.provider, source.device_type), str(source.id)),
        )
        # The planner overestimates the merge and compiles it, which takes far longer than running it.
        db_session.execute(text("SET LOCAL jit = off"))
        rows = db_session.execute(
            _MERGE, {**params, "source_ids": [s.id for s in ordered], "positions": list(range(len(ordered)))}
        )
        return [MergedDay(row.type_id, row.day, row.zone_offset, float(row.sum), row.count) for row in rows]

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
