from collections.abc import Iterable, Iterator
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import Row, text

from app.database import DbSession
from app.models import EventRecordAggregate, SeriesAggregate
from app.repositories.aggregate_repository import AggregateRepository
from app.schemas.enums import (
    AGGREGATION_METHOD_BY_TYPE,
    AggregationMethod,
    ComputedBy,
    EventCategory,
    PeriodKind,
    get_series_type_id,
)
from app.schemas.model_crud.activities import CalendarPeriod

# A local day reaches up to 14 hours either side of its UTC date.
_OFFSET_REACH = timedelta(hours=14)
# Days further apart than this are rolled up by separate range scans.
_MAX_GAP = timedelta(days=7)

_STATS = """sum(s.value) AS sum, avg(s.value) AS avg, min(s.value) AS min, max(s.value) AS max,
    (array_agg(s.value ORDER BY s.recorded_at DESC))[1] AS last, count(*) AS count"""
_SAMPLE_DAY = "((s.recorded_at AT TIME ZONE 'UTC') + coalesce(s.zone_offset, '+00:00')::interval)::date"

_DAY_STATS = text(f"""
    SELECT s.series_type_definition_id, {_SAMPLE_DAY} AS day,
        min(coalesce(s.zone_offset, '+00:00')) AS zone_offset, {_STATS}
    FROM series_sample s
    WHERE s.data_source_id = :source_id AND s.recorded_at >= :lo AND s.recorded_at < :hi
        AND s.is_daily_total IS NOT TRUE AND {_SAMPLE_DAY} = ANY(:days)
    GROUP BY 1, 2
""")

_DELETE_DAYS = text("""
    DELETE FROM series_aggregate
    WHERE data_source_id = :source_id AND computed_by = :computed_by AND period_kind = :period_kind
        AND period_start >= :lo AND period_start < :hi
        AND ((period_start AT TIME ZONE 'UTC') + zone_offset::interval)::date = ANY(:days)
""")

_SESSIONS = text("""
    SELECT id,
        coalesce(((start_datetime AT TIME ZONE 'UTC') + coalesce(zone_offset, '+00:00')::interval)::date
            < CAST(:frozen_before AS date), false) AS frozen
    FROM event_record
    WHERE data_source_id = :source_id AND category = ANY(:categories)
        AND start_datetime < :hi AND end_datetime >= :lo
""")

_SESSION_STATS = text(f"""
    SELECT er.id AS record_id, s.series_type_definition_id, {_STATS}
    FROM event_record er
    JOIN series_sample s ON s.data_source_id = er.data_source_id
        AND s.recorded_at >= er.start_datetime AND s.recorded_at <= er.end_datetime
        AND s.is_daily_total IS NOT TRUE
    WHERE er.id = ANY(:record_ids)
    GROUP BY 1, 2
""")

_DELETE_SESSIONS = text("""
    DELETE FROM event_record_aggregate WHERE computed_by = :computed_by AND record_id = ANY(:record_ids)
""")

_DAYS_BEFORE = text(f"""
    SELECT DISTINCT {_SAMPLE_DAY} AS day FROM series_sample s
    WHERE s.data_source_id = :source_id AND s.recorded_at < :hi AND {_SAMPLE_DAY} < :cutoff
""")

_SESSION_CATEGORIES = [EventCategory.SLEEP.value, EventCategory.WORKOUT.value]
# A sum is kept only where the series is summed: a day's heart rates add up past numeric(10, 3).
_SUMMED_TYPE_IDS = frozenset(
    get_series_type_id(series_type)
    for series_type, method in AGGREGATION_METHOD_BY_TYPE.items()
    if method is AggregationMethod.SUM
)


class SeriesRollupRepository:
    """Rolls a source's samples up into open_wearables rows: one per series and local day, one per series and
    sleep or workout. A day is recomputed whole, so its rows always reflect the samples stored now."""

    def __init__(self) -> None:
        self.series_aggregate_repo = AggregateRepository(SeriesAggregate)
        self.event_aggregate_repo = AggregateRepository(EventRecordAggregate)

    def roll_up(
        self, db_session: DbSession, source_id: UUID, days: Iterable[date], frozen_before: date | None = None
    ) -> int:
        """Recompute the source's day rows for ``days`` and its sessions on them; returns the day rows written.

        Days before ``frozen_before`` and sessions started before it have lost their samples to retention,
        so they are never recomputed: they only gain rows they lack, from whatever samples came late.
        """
        written = 0
        for run in _runs(sorted(set(days))):
            lo = _utc_midnight(run[0]) - _OFFSET_REACH
            hi = _utc_midnight(run[-1]) + timedelta(days=1) + _OFFSET_REACH
            written += self._roll_up_days(db_session, source_id, run, lo, hi, frozen_before)
            self._roll_up_sessions(db_session, source_id, lo, hi, frozen_before)
        return written

    def days_before(self, db_session: DbSession, source_id: UUID, cutoff: date) -> list[date]:
        """Local days before ``cutoff`` on which the source still has samples."""
        hi = _utc_midnight(cutoff) + _OFFSET_REACH
        rows = db_session.execute(_DAYS_BEFORE, {"source_id": source_id, "hi": hi, "cutoff": cutoff})
        return [row.day for row in rows]

    def _roll_up_days(
        self,
        db_session: DbSession,
        source_id: UUID,
        days: list[date],
        lo: datetime,
        hi: datetime,
        frozen_before: date | None,
    ) -> int:
        fresh = [day for day in days if frozen_before is None or day >= frozen_before]
        params = {"source_id": source_id, "lo": lo, "hi": hi, "days": days}
        if fresh:
            db_session.execute(
                _DELETE_DAYS,
                {**params, "days": fresh, "computed_by": ComputedBy.OPEN_WEARABLES, "period_kind": PeriodKind.DAY},
            )
        rows: dict[bool, list[dict]] = {True: [], False: []}
        for row in db_session.execute(_DAY_STATS, params):
            period = CalendarPeriod.of_date(row.day, row.zone_offset)
            rows[row.day in fresh].append(
                {
                    "data_source_id": source_id,
                    "series_type_definition_id": row.series_type_definition_id,
                    "period_kind": PeriodKind.DAY,
                    "period_start": period.start,
                    "period_end": period.end,
                    "zone_offset": period.zone_offset,
                    "computed_by": ComputedBy.OPEN_WEARABLES,
                    **_stats(row),
                }
            )
        return self._write(self.series_aggregate_repo, db_session, rows)

    def _roll_up_sessions(
        self, db_session: DbSession, source_id: UUID, lo: datetime, hi: datetime, frozen_before: date | None
    ) -> None:
        params = {
            "source_id": source_id,
            "lo": lo,
            "hi": hi,
            "categories": _SESSION_CATEGORIES,
            "frozen_before": frozen_before,
        }
        frozen_by_id = {row.id: row.frozen for row in db_session.execute(_SESSIONS, params)}
        if not frozen_by_id:
            return
        if fresh_ids := [record_id for record_id, frozen in frozen_by_id.items() if not frozen]:
            db_session.execute(_DELETE_SESSIONS, {"computed_by": ComputedBy.OPEN_WEARABLES, "record_ids": fresh_ids})
        rows: dict[bool, list[dict]] = {True: [], False: []}
        for row in db_session.execute(_SESSION_STATS, {"record_ids": list(frozen_by_id)}):
            rows[not frozen_by_id[row.record_id]].append(
                {
                    "record_id": row.record_id,
                    "series_type_definition_id": row.series_type_definition_id,
                    "computed_by": ComputedBy.OPEN_WEARABLES,
                    **_stats(row),
                }
            )
        self._write(self.event_aggregate_repo, db_session, rows)

    @staticmethod
    def _write(repo: AggregateRepository, db_session: DbSession, rows: dict[bool, list[dict]]) -> int:
        """Fresh rows (True) replace what the delete cleared; frozen rows (False) fill gaps only."""
        written = repo.upsert(db_session, rows[True]) if rows[True] else 0
        if rows[False]:
            written += repo.insert_missing(db_session, rows[False])
        return written


def _stats(row: Row) -> dict:
    stats = {column: getattr(row, column) for column in ("sum", "avg", "min", "max", "last", "count")}
    if row.series_type_definition_id not in _SUMMED_TYPE_IDS:
        stats["sum"] = None
    return stats


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time(), timezone.utc)


def _runs(days: list[date]) -> Iterator[list[date]]:
    """Split sorted days where they are more than a week apart, so each range scan stays short."""
    run: list[date] = []
    for day in days:
        if run and day - run[-1] > _MAX_GAP:
            yield run
            run = []
        run.append(day)
    if run:
        yield run
