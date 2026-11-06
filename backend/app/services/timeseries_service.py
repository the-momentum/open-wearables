import threading
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import event as sa_event

from app.config import settings
from app.database import DbSession
from app.integrations import rollup_queue
from app.models import DataSource, SeriesAggregate, SeriesSample
from app.repositories import ArchivalSettingRepository, DataPointSeriesRepository
from app.repositories.data_point_series_repository import AggregatedSample, Coverage, StoredWindow, WriteCounts
from app.repositories.repositories import SourceRanking
from app.repositories.series_aggregate_repository import SampleDay, SeriesAggregateRepository, StaleDays
from app.repositories.series_reconcile_repository import RECONCILED_SERIES, SeriesReconcileRepository
from app.schemas.enums import (
    BUCKET_SIZES,
    PERIOD_RESOLUTIONS,
    ComputedBy,
    PeriodKind,
    Resolution,
    SeriesType,
    SourceSelection,
    get_series_type_from_id,
    get_series_type_id,
    get_series_type_unit,
)
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.model_crud.activities import (
    CalendarPeriod,
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.responses.activity import SeriesStats, TimeSeriesSample
from app.schemas.utils import (
    PaginatedResponse,
    Pagination,
    SourceMetadata,
    TimeseriesMetadata,
)
from app.services.aggregate_backfill_service import days_from_samples
from app.services.outgoing_webhooks import svix as svix_service
from app.services.outgoing_webhooks.events import on_timeseries_batch_saved
from app.services.priority_service import priority_service
from app.services.services import AppService
from app.utils.context import current_sync_payload
from app.utils.exceptions import ReconcileWindowTooLargeError
from app.utils.pagination import decode_date_cursor, encode_bucket_cursor, encode_cursor, encode_date_cursor
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def _best_per_bucket(samples: list[AggregatedSample], ranking: SourceRanking) -> list[AggregatedSample]:
    """Per bucket and series type, only the best-ranked source's row; the order stays."""

    def key(sample: AggregatedSample) -> tuple:
        source = sample.data_source
        return (*ranking.rank(source.provider, source.device_type), str(source.id))

    best: dict[tuple[datetime, int], AggregatedSample] = {}
    for sample in samples:
        held = best.get((sample.bucket, sample.series_type_definition_id))
        if held is None or key(sample) < key(held):
            best[(sample.bucket, sample.series_type_definition_id)] = sample
    return [s for s in samples if best[(s.bucket, s.series_type_definition_id)] is s]


@dataclass(frozen=True)
class _MergedDayRow:
    """A movement series' day merged across a user's sources (source_selection=reconcile), read like a day row:
    no one device's, so it names no data source."""

    series_type_definition_id: int
    period_start: datetime
    zone_offset: str
    sum: Decimal
    count: int
    data_source_id: None = None
    avg: None = None
    min: None = None
    max: None = None
    last: None = None
    computed_by: ComputedBy = ComputedBy.OPEN_WEARABLES


# A day's value as a period read takes it: a source's day row, its day counted from samples, or a merged day.
_DayRow = SeriesAggregate | SampleDay | _MergedDayRow


def _best_per_day(
    rows: list[tuple[SeriesAggregate | SampleDay, date]], sources: dict[UUID, DataSource], ranking: SourceRanking
) -> list[tuple[SeriesAggregate | SampleDay, date]]:
    """Per series type and local day, only the best-ranked source's row; a tie goes to the row counting more."""

    def key(row: SeriesAggregate | SampleDay) -> tuple:
        source = sources[row.data_source_id]
        return (*ranking.rank(source.provider, source.device_type), -row.count, str(source.id))

    best: dict[tuple[int, date], tuple[SeriesAggregate | SampleDay, date]] = {}
    for row, day in rows:
        held = best.get((row.series_type_definition_id, day))
        if held is None or key(row) < key(held[0]):
            best[(row.series_type_definition_id, day)] = (row, day)
    return sorted(best.values(), key=lambda pair: pair[1])


def _trim_to_whole_buckets(
    samples: list[AggregatedSample],
    limit: int,
    truncated: bool,
) -> tuple[list[AggregatedSample], bool]:
    """Cut at a bucket boundary: the cursor is a bucket start, so a bucket split across two
    pages would be skipped or repeated. Rows arrive ordered by bucket."""
    seen, previous = 0, None
    for index, sample in enumerate(samples):
        if sample.bucket != previous:
            if seen == limit:
                return samples[:index], True
            seen += 1
            previous = sample.bucket
    return samples, truncated


def _to_sample(
    timestamp: datetime,
    zone_offset: str | None,
    series_type_definition_id: int,
    value: Decimal,
    is_daily_total: bool | None,
    data_source: DataSource | None,
    *,
    window_seconds: int | None = None,
    period_end: datetime | None = None,
    computed_by: ComputedBy | None = None,
    stats: SeriesStats | None = None,
) -> TimeSeriesSample:
    series_type = get_series_type_from_id(series_type_definition_id)
    source = None
    if data_source is not None:
        source = SourceMetadata(
            provider=data_source.provider or "unknown",
            source=data_source.source,
            device=data_source.device_model,
            device_type=data_source.device_type,
            device_id=data_source.device_id,
        )
    return TimeSeriesSample(
        timestamp=timestamp,
        zone_offset=zone_offset,
        type=series_type,
        value=float(value),
        unit=get_series_type_unit(series_type),
        source=source,
        is_daily_total=is_daily_total,
        window_seconds=window_seconds,
        period_end=period_end,
        computed_by=computed_by,
        stats=stats,
    )


# Open ends of a period read; far enough from date.min/max that a day's UTC bounds still fit.
_NO_START, _NO_END = date(1900, 1, 1), date(9000, 1, 1)
# Day rows one page of periods may load, as the bucket path caps its rows.
_PERIOD_ROWS_PER_PAGE = 5000


def _clamp(at: datetime | None, first: date, last: date) -> datetime | None:
    if at is None:
        return None
    lowest, highest = datetime.combine(first, time(), at.tzinfo), datetime.combine(last, time(), at.tzinfo)
    return min(max(at, lowest), highest)


def _period_of(day: date, kind: PeriodKind) -> date:
    """First day of the week (Monday) or month a day falls in."""
    if kind is PeriodKind.WEEK:
        return day - timedelta(days=day.weekday())
    if kind is PeriodKind.MONTH:
        return day.replace(day=1)
    return day


def _shift(period: date, kind: PeriodKind, periods: int) -> date:
    """The period ``periods`` after (or, negative, before) the one starting on ``period``."""
    if kind is PeriodKind.MONTH:
        months = period.year * 12 + period.month - 1 + periods
        return date(months // 12, months % 12 + 1, 1)
    return period + timedelta(days=periods * (7 if kind is PeriodKind.WEEK else 1))


def _combine(rows: list[_DayRow]) -> SeriesStats:
    """One period's statistics from its days: sums add up, extremes stay extreme, the average is
    the mean of the daily averages, and the last value is the latest day's."""

    def values(column: str) -> list[float]:
        return [float(value) for row in rows if (value := getattr(row, column)) is not None]

    avgs, mins, maxs, sums, lasts = (values(c) for c in ("avg", "min", "max", "sum", "last"))
    return SeriesStats(
        avg=sum(avgs) / len(avgs) if avgs else None,
        min=min(mins) if mins else None,
        max=max(maxs) if maxs else None,
        sum=sum(sums) if sums else None,
        last=lasts[-1] if lasts else None,
        count=sum(row.count for row in rows),
    )


def _value_of(stats: SeriesStats, series_type: SeriesType) -> float:
    """The statistic the series is read by, else whichever one the provider sent."""
    canonical = getattr(stats, get_aggregation_method(series_type).value)
    if canonical is not None:
        return canonical
    return next(v for v in (stats.avg, stats.max, stats.min, stats.sum, stats.last) if v is not None)


def _page(
    data: list[TimeSeriesSample],
    params: TimeSeriesQueryParams,
    has_more: bool,
    next_cursor: str | None,
    previous_cursor: str | None,
    total_count: int | None = None,
) -> PaginatedResponse[TimeSeriesSample]:
    return PaginatedResponse(
        data=data,
        pagination=Pagination(
            has_more=has_more,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
            total_count=total_count,
        ),
        metadata=TimeseriesMetadata(
            resolution=params.resolution,
            sample_count=len(data),
            start_time=params.start_datetime,
            end_time=params.end_datetime,
        ),
    )


class TimeSeriesService(
    AppService[
        DataPointSeriesRepository,
        SeriesSample,
        TimeSeriesSampleCreate,
        TimeSeriesSampleUpdate,
    ],
):
    """Coordinated access to unified device time series samples."""

    def __init__(self):
        super().__init__(crud_model=DataPointSeriesRepository, model=SeriesSample)
        self.series_aggregate_repo = SeriesAggregateRepository()

    def bulk_create_samples(
        self,
        db_session: DbSession,
        samples: (list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate]),
    ) -> WriteCounts:
        counts = self.crud.bulk_create(db_session, samples)  # ty:ignore[invalid-argument-type]
        # Day and session values are not samples any more, so they are not series webhook samples either.
        samples_copy = [
            s for s in samples if getattr(s, "period", None) is None and getattr(s, "session", None) is None
        ]
        # Read here, not in the thread: a ContextVar does not cross into one.
        sync = current_sync_payload()

        @sa_event.listens_for(db_session, "after_commit", once=True)
        def _start_webhook_thread(session: DbSession) -> None:  # noqa: ARG001
            if not svix_service.is_enabled():
                return
            threading.Thread(
                target=self._emit_timeseries_webhooks,
                args=(samples_copy, sync),
                daemon=True,
            ).start()

        return counts

    def has_samples_in_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        source: str,
        device_model: str | None,
        series_types: Iterable[SeriesType],
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> bool:
        return self.crud.has_samples_in_range(
            db_session, user_id, source, device_model, series_types, start_datetime, end_datetime
        )

    def stored_in_windows(
        self, db_session: DbSession, user_id: UUID, windows: Sequence[StoredWindow]
    ) -> list[Coverage]:
        """Per window, what the user's stored samples of its type and writer app cover."""
        return self.crud.stored_in_windows(db_session, user_id, windows)

    @staticmethod
    def _emit_timeseries_webhooks(
        samples: list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate],
        sync: dict[str, str] | None = None,
    ) -> None:
        """Emit one webhook event per (user, provider, series_type) batch."""
        if not samples:
            return
        try:
            groups: dict[tuple[UUID, str, str], list[Any]] = defaultdict(list)
            for s in samples:
                key = (s.user_id, s.provider or s.source or "unknown", s.series_type.value)
                groups[key].append(s)
            for (user_id, provider, series_type_value), group_samples in groups.items():
                sorted_samples = sorted(group_samples, key=lambda s: s.recorded_at)
                series_type_enum = SeriesType(series_type_value)
                unit = get_series_type_unit(series_type_enum)
                webhook_samples = [
                    {
                        "timestamp": s.recorded_at.isoformat(),
                        "zone_offset": s.zone_offset,
                        "type": series_type_value,
                        "value": float(s.value),
                        "unit": unit,
                        "source": {"provider": provider, "device": s.device_model},
                        "is_daily_total": s.is_daily_total,
                        "window_seconds": s.window_seconds,
                    }
                    for s in sorted_samples
                ]
                on_timeseries_batch_saved(
                    user_id=user_id,
                    provider=provider,
                    series_type=series_type_value,
                    sample_count=len(sorted_samples),
                    start_time=sorted_samples[0].recorded_at.isoformat(),
                    end_time=sorted_samples[-1].recorded_at.isoformat(),
                    samples=webhook_samples,
                    sync=sync,
                )
        except Exception:
            logger.warning("Failed to emit timeseries webhooks", exc_info=True)

    def get_total_count(self, db_session: DbSession) -> int:
        """Get total count of all data points."""
        return self.crud.get_total_count(db_session)

    def get_approximate_total_count(self, db_session: DbSession) -> int:
        """Get an approximate total count of all data points (planner statistics, no scan)."""
        return self.crud.get_approximate_total_count(db_session)

    def get_approximate_archived_count(self, db_session: DbSession) -> int:
        """Get an approximate count of archived data points (planner statistics, no scan)."""
        return self.crud.get_approximate_archived_count(db_session)

    def get_approximate_aggregate_count(self, db_session: DbSession) -> int:
        """Approximate number of day and session rows (planner statistics, no scan)."""
        return self.crud.get_approximate_aggregate_count(db_session)

    def get_count_in_range(self, db_session: DbSession, start_datetime: datetime, end_datetime: datetime) -> int:
        """Get count of data points within a datetime range."""
        return self.crud.get_count_in_range(db_session, start_datetime, end_datetime)

    def get_daily_histogram(
        self,
        db_session: DbSession,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[int]:
        """Get daily histogram of data points for the given date range."""
        return self.crud.get_daily_histogram(db_session, start_datetime, end_datetime)

    def get_count_by_source(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by source."""
        return self.crud.get_count_by_source(db_session)

    def _winning_sources(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        sample_sources: set[UUID] | None = None,
    ) -> dict[int, UUID]:
        """Resolve one data source per series type, using the ranking sleep and summaries use."""
        ranking = priority_service.get_source_ranking(db_session)
        return self.crud.winning_source_by_series_type(db_session, params, types, user_id, ranking, sample_sources)

    def _aggregated_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        source_by_type: dict[int, UUID] | None = None,
        ranking: SourceRanking | None = None,
    ) -> PaginatedResponse[TimeSeriesSample]:
        """Downsampled variant of :meth:`get_timeseries`.

        total_count stays unset: counting buckets would scan the whole requested range, which
        is the work the bucket cap exists to avoid.
        """
        rows, truncated = self.crud.get_aggregated_samples(db_session, params, types, user_id, source_by_type)
        if ranking is not None:
            rows = _best_per_bucket(rows, ranking)
        samples, has_more = _trim_to_whole_buckets(rows, params.limit or 50, truncated)
        is_backward = bool(params.cursor and params.cursor.startswith("prev_"))
        if is_backward:
            # Paging back reads newest-first; responses are always ascending.
            samples = list(reversed(samples))
        # Paging back, has_more means older buckets exist, so it gates previous_cursor too.
        has_next = bool(samples) and has_more
        has_previous = bool(samples) and bool(params.cursor) and (has_more or not is_backward)

        window = int(BUCKET_SIZES[params.resolution].total_seconds())
        return _page(
            data=[
                _to_sample(
                    s.bucket,
                    s.zone_offset,
                    s.series_type_definition_id,
                    s.value,
                    s.is_daily_total,
                    s.data_source,
                    window_seconds=window,
                )
                for s in samples
            ],
            params=params,
            has_more=has_more,
            next_cursor=encode_bucket_cursor(samples[-1].bucket) if has_next else None,
            previous_cursor=encode_bucket_cursor(samples[0].bucket, "prev") if has_previous else None,
        )

    def _period_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        source_selection: SourceSelection = SourceSelection.ALL,
    ) -> PaginatedResponse[TimeSeriesSample]:
        """Day, week and month values from series_aggregate, the provider's day before ours.

        Weeks start on Monday and months on the 1st, by the local day; a week or month is built from
        its days within the requested range. Pages hold ``limit`` periods; the cursor is a period's
        first day. With per_period, each day keeps only its best-ranked source, and a week or month is
        built from those days whichever source each came from. With reconcile too, a merged series' day two
        sources hold is their merged value instead (see :meth:`_reconciled_days`).

        Until the rollup is on and caught up with the history, a day no row holds is counted from its samples.
        After that, only the days the rollup has not caught up with yet are: the rollup queue names them, asked
        while the first query runs.
        """
        kind = PERIOD_RESOLUTIONS[params.resolution]
        per_range = source_selection is SourceSelection.PER_RANGE
        reconcile = source_selection is SourceSelection.RECONCILE
        ranked = source_selection in (SourceSelection.PER_PERIOD, SourceSelection.RECONCILE)
        ranking = priority_service.get_source_ranking(db_session) if ranked else None
        first_day = max(params.start_datetime.date(), _NO_START) if params.start_datetime else _NO_START
        last_day = (
            min((params.end_datetime - timedelta(microseconds=1)).date(), _NO_END) if params.end_datetime else _NO_END
        )
        # The whole range, whatever page: priority must pick the same source on every page.
        range_days = (first_day, last_day)
        backward = False
        if params.cursor:
            cursor_period, direction = decode_date_cursor(params.cursor)
            cursor_period = min(max(cursor_period, _NO_START), _NO_END)
            backward = direction == "prev"
            if backward:
                last_day = cursor_period - timedelta(days=1)
            else:
                first_day = _shift(cursor_period, kind, 1)

        # Start at the first (or last) day that holds data, then read only the days of limit + 1 periods,
        # so a sparse range is not paged through empty and a page never scans the whole range.
        repo = self.series_aggregate_repo
        from_samples = days_from_samples(db_session)
        source_ids: set[UUID] = set()
        if per_range or not from_samples:
            source_ids = {source_id for _, source_id in repo._pairs(db_session, user_id, params, types, None)}
        # Asked on a worker thread while the next query runs; answered empty when every day is read from samples.
        pending_stale = repo.stale_days_soon(db_session, source_ids, *range_days) if not from_samples else dict
        source_by_type = None
        if per_range:
            # Priority picks among the sources holding something on these days, samples counted where they are read.
            stale = pending_stale()
            pending_stale = lambda: stale  # noqa: E731
            sample_sources = source_ids if from_samples else set(stale)
            source_by_type = self._winning_sources(db_session, user_id, types, params, sample_sources)

        def edge_day(first: date, last: date, latest: bool, starts: Any = None) -> date | None:
            """The outermost day holding a row, or with ``from_samples`` a sample, or one the rollup is behind on."""
            days = [repo.edge_day(db_session, user_id, params, types, first, last, source_by_type, latest, starts)]
            if from_samples:
                days.append(
                    repo.sample_edge_day(db_session, user_id, params, types, first, last, source_by_type, latest)
                )
            read_sources = set(source_by_type.values()) if source_by_type is not None else set(stale)
            days.extend(day for source_id in read_sources for day in stale.get(source_id, ()) if first <= day <= last)
            days = [day for day in days if day is not None]
            return (max(days) if latest else min(days)) if days else None

        edges = repo.edge_rows(db_session, user_id, params, types, first_day, last_day, source_by_type, backward)
        stale = pending_stale()
        if not edges and not from_samples and not stale:
            return _page(data=[], params=params, has_more=False, next_cursor=None, previous_cursor=None)
        # A period is up to two rows (the provider's and ours) a day for every series of every source holding
        # data here; with all of them asked for, a page of `limit` periods could be hundreds of thousands of rows.
        days_per_period = {PeriodKind.DAY: 1, PeriodKind.WEEK: 7, PeriodKind.MONTH: 31}[kind]
        limit = max(1, min(params.limit or 50, _PERIOD_ROWS_PER_PAGE // (2 * max(len(edges), 1) * days_per_period)))
        if reconcile:
            # A shorter page rather than a refused one: the merge budget is per page.
            limit = max(1, min(limit, settings.reconcile_on_the_fly_max_days // days_per_period))
        edge = edge_day(first_day, last_day, backward, edges.values() if edges else None)
        if edge is None:
            return _page(data=[], params=params, has_more=False, next_cursor=None, previous_cursor=None)
        if backward:
            last_day = edge
            window = (max(first_day, _shift(_period_of(last_day, kind), kind, -limit)), last_day)
        else:
            first_day = edge
            window = (
                first_day,
                min(last_day, _shift(_period_of(first_day, kind), kind, limit + 1) - timedelta(days=1)),
            )
        device_rows = repo.day_rows_or_samples(
            db_session, user_id, types, *window, from_samples, params, source_by_type, stale=stale
        )
        sources = self.crud._sources_by_id(db_session, {row.data_source_id for row, _ in device_rows})
        rows: Sequence[tuple[_DayRow, date]] = device_rows
        if reconcile and ranking is not None:
            # The period read past the page only tells whether another page follows: it is not merged.
            held = sorted({_period_of(day, kind) for _, day in device_rows})
            shown_periods = set(held[-limit:] if backward else held[:limit])
            shown = {day for _, day in device_rows if _period_of(day, kind) in shown_periods}
            rows = self._reconciled_days(
                db_session, user_id, types, device_rows, sources, ranking, from_samples, stale, shown
            )
        elif ranking is not None:
            rows = _best_per_day(device_rows, sources, ranking)

        groups: dict[tuple[date, UUID | None, int], list[_DayRow]] = defaultdict(list)
        for row, day in rows:
            source_id = None if ranking is not None else row.data_source_id
            groups[(_period_of(day, kind), source_id, row.series_type_definition_id)].append(row)
        periods = sorted({period for period, _, _ in groups})
        overflow = len(periods) > limit
        periods = periods[-limit:] if backward else periods[:limit]
        rest = (first_day, window[0] - timedelta(days=1)) if backward else (window[1] + timedelta(days=1), last_day)
        has_more = overflow or (rest[0] <= rest[1] and edge_day(*rest, False) is not None)

        shown = set(periods)
        data = []
        for (period, _, type_id), period_rows in sorted(
            groups.items(), key=lambda item: (item[0][0], str(item[0][1]), item[0][2])
        ):
            if period not in shown:
                continue
            # A period built from several sources' days names none of them.
            period_sources = {row.data_source_id for row in period_rows}
            # A merged day's source is no device: it is not among them.
            source_id = period_sources.pop() if len(period_sources) == 1 else None
            source = sources.get(source_id) if source_id is not None else None
            zone_offset = period_rows[0].zone_offset
            stats = _combine(period_rows)
            data.append(
                _to_sample(
                    CalendarPeriod.of_date(period, zone_offset).start,
                    zone_offset,
                    type_id,
                    Decimal(str(_value_of(stats, get_series_type_from_id(type_id)))),
                    None,
                    source,
                    # The end takes the last day's offset: a clock change inside the period moves it by an hour.
                    period_end=CalendarPeriod.of_date(_shift(period, kind, 1), period_rows[-1].zone_offset).start,
                    computed_by=period_rows[0].computed_by if kind is PeriodKind.DAY else ComputedBy.OPEN_WEARABLES,
                    stats=stats,
                )
            )

        has_next = bool(periods) and has_more
        has_previous = bool(periods) and bool(params.cursor) and (has_more or not backward)
        return _page(
            data=data,
            params=params,
            has_more=has_more,
            next_cursor=encode_date_cursor(periods[-1]) if has_next else None,
            previous_cursor=encode_date_cursor(periods[0], "prev") if has_previous else None,
        )

    def _reconciled_days(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        rows: list[tuple[SeriesAggregate | SampleDay, date]],
        sources: dict[UUID, DataSource],
        ranking: SourceRanking,
        from_samples: bool,
        stale: StaleDays,
        shown: set[date] | None = None,
    ) -> Sequence[tuple[_DayRow, date]]:
        """The devices' day rows of a page, with each RECONCILED_SERIES day of ``shown`` two of them hold replaced by
        its merged value: the stored one unless a source has newer samples (``stale``), else merged now (at most
        RECONCILE_ON_THE_FLY_MAX_DAYS days, queued to be stored with reconcile on). A day whose best-ranked source
        holds no samples keeps that source's row."""
        if not rows:
            return rows
        merged_series = RECONCILED_SERIES & set(types) if types else RECONCILED_SERIES
        if not merged_series:
            return _best_per_day(rows, sources, ranking)
        merged_type_ids = {get_series_type_id(series_type) for series_type in merged_series}
        reconcile_repo = SeriesReconcileRepository()
        first_day, last_day = min(day for _, day in rows), max(day for _, day in rows)
        reconciled = reconcile_repo.reconciled_source(db_session, user_id)
        sources_of: dict[tuple[int, date], set[UUID]] = defaultdict(set)
        for row, day in rows:
            sources_of[(row.series_type_definition_id, day)].add(row.data_source_id)
        # A stored merge is out of date only when a source of that series and day has newer samples queued.
        stored = {
            key: row
            for key, row in (
                reconcile_repo.day_rows(db_session, reconciled.id, sorted(merged_type_ids), first_day, last_day)
                if reconciled
                else {}
            ).items()
            if not any(key[1] in stale.get(source_id, ()) for source_id in sources_of.get(key, ()))
        }
        # Retention has deleted these days' samples: nothing is left to merge, the best source's day stands.
        frozen_before = ArchivalSettingRepository().deleted_before(db_session)
        candidates = {
            key: source_ids
            for key, source_ids in sources_of.items()
            if key[0] in merged_type_ids
            and key not in stored
            and len(source_ids) > 1
            and (shown is None or key[1] in shown)
            and (frozen_before is None or key[1] >= frozen_before)
        }
        if candidates:
            ids = sorted({source_id for source_ids in candidates.values() for source_id in source_ids}, key=str)
            days_asked = sorted({day for _, day in candidates})
            with_samples = reconcile_repo.sources_with_samples(db_session, ids, days_asked, sorted(merged_type_ids))

            def best(source_ids: set[UUID]) -> UUID:
                return min(
                    source_ids, key=lambda s: (*ranking.rank(sources[s].provider, sources[s].device_type), str(s))
                )

            candidates = {key: ids for key, ids in candidates.items() if best(ids) in with_samples}
        needed = set(candidates)
        days = sorted({day for _, day in needed})
        queued = bool(days) and settings.reconcile_enabled and not from_samples
        if queued:
            try:
                rollup_queue.queue_reconcile_days((user_id, day) for day in days)
            except Exception as exc:
                # Queueing only saves a later read the merge; this read merges the days itself all the same.
                logger.warning("Reconcile could not queue merged days to be stored", exc_info=exc)
                queued = False
        if len(days) > settings.reconcile_on_the_fly_max_days:
            raise ReconcileWindowTooLargeError(len(days), settings.reconcile_on_the_fly_max_days, queued)

        merged: dict[tuple[int, date], _MergedDayRow] = {}
        merging = reconcile_repo.merge(db_session, user_id, days, ranking, sorted(merged_type_ids)) if days else ()
        for day in merging:
            if (day.type_id, day.day) in needed:
                merged[(day.type_id, day.day)] = _MergedDayRow(
                    series_type_definition_id=day.type_id,
                    period_start=CalendarPeriod.of_date(day.day, day.zone_offset).start,
                    zone_offset=day.zone_offset,
                    sum=Decimal(str(day.sum)),
                    count=day.count,
                )
        taken = stored.keys() | merged.keys()
        devices = [(row, day) for row, day in rows if (row.series_type_definition_id, day) not in taken]
        result: list[tuple[_DayRow, date]] = [
            *_best_per_day(devices, sources, ranking),
            *((row, key[1]) for key, row in stored.items()),
            *((row, key[1]) for key, row in merged.items()),
        ]
        return sorted(result, key=lambda pair: pair[1])

    def get_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        source_selection: SourceSelection = SourceSelection.ALL,
    ) -> PaginatedResponse[TimeSeriesSample]:
        if params.resolution in PERIOD_RESOLUTIONS:
            # An open end stays an open end: the day bounds a read computes around a far date must still be dates.
            params = params.model_copy(
                update={
                    "start_datetime": _clamp(params.start_datetime, _NO_START, _NO_END),
                    "end_datetime": _clamp(params.end_datetime, _NO_START, _NO_END),
                }
            )
        if params.resolution in PERIOD_RESOLUTIONS:
            return self._period_timeseries(db_session, user_id, types, params, source_selection)
        source_by_type = None
        if source_selection is SourceSelection.PER_RANGE:
            source_by_type = self._winning_sources(db_session, user_id, types, params)
        ranking = (
            priority_service.get_source_ranking(db_session) if source_selection is SourceSelection.PER_PERIOD else None
        )
        if params.resolution is not Resolution.RAW:
            return self._aggregated_timeseries(db_session, user_id, types, params, source_by_type, ranking)

        samples, total_count = self.crud.get_samples(db_session, params, types, user_id, source_by_type)

        limit = params.limit or 50
        has_more = len(samples) > limit

        # Check if this is backward pagination
        is_backward = params.cursor and params.cursor.startswith("prev_")

        # Trim to limit
        if has_more:
            samples = samples[-limit:] if is_backward else samples[:limit]

        # Generate cursors
        next_cursor = None
        previous_cursor = None

        if samples:
            # Always generate next_cursor if has_more
            if has_more:
                last_sample = samples[-1][0]
                next_cursor = encode_cursor(last_sample.recorded_at, last_sample.id, "next")

            # Generate previous_cursor only if:
            # 1. We used a cursor to get here (not the first page)
            # 2. There are more items before (for backward) OR we're doing forward navigation
            if params.cursor:
                # For backward navigation: only set previous_cursor if has_more
                # For forward navigation: always set previous_cursor
                if is_backward:
                    if has_more:
                        first_sample = samples[0][0]
                        previous_cursor = encode_cursor(first_sample.recorded_at, first_sample.id, "prev")
                else:
                    first_sample = samples[0][0]
                    previous_cursor = encode_cursor(first_sample.recorded_at, first_sample.id, "prev")

        data = [
            _to_sample(
                sample.recorded_at,
                sample.zone_offset,
                sample.series_type_definition_id,
                sample.value,
                sample.is_daily_total,
                data_source,
                window_seconds=sample.window_seconds,
            )
            for sample, data_source in samples
        ]

        return _page(data, params, has_more, next_cursor, previous_cursor, total_count)


timeseries_service = TimeSeriesService()
