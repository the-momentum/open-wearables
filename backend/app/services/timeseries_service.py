import threading
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from sqlalchemy import event as sa_event

from app.database import DbSession
from app.models import DataSource, ProviderPriority, SeriesAggregate, SeriesSample
from app.repositories import DataPointSeriesRepository, ProviderPriorityRepository
from app.repositories.data_point_series_repository import AggregatedSample, WriteCounts
from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
from app.repositories.series_aggregate_repository import SampleDay, SeriesAggregateRepository
from app.schemas.enums import (
    BUCKET_SIZES,
    PERIOD_RESOLUTIONS,
    ComputedBy,
    PeriodKind,
    Resolution,
    SeriesType,
    get_series_type_from_id,
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
from app.services.outgoing_webhooks import svix as svix_service
from app.services.outgoing_webhooks.events import on_timeseries_batch_saved
from app.services.services import AppService
from app.utils.context import current_sync_payload
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import decode_date_cursor, encode_bucket_cursor, encode_cursor, encode_date_cursor


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


def _combine(rows: list[SeriesAggregate | SampleDay]) -> SeriesStats:
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

    def __init__(self, log: Logger):
        super().__init__(crud_model=DataPointSeriesRepository, model=SeriesSample, log=log)
        self.provider_priority_repo = ProviderPriorityRepository(ProviderPriority)
        self.device_type_priority_repo = DeviceTypePriorityRepository()
        self.series_aggregate_repo = SeriesAggregateRepository()

    def bulk_create_samples(
        self,
        db_session: DbSession,
        samples: (list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate]),
    ) -> WriteCounts:
        counts = self.crud.bulk_create(db_session, samples)  # ty:ignore[invalid-argument-type]
        samples_copy = list(samples)
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
            getLogger(__name__).warning("Failed to emit timeseries webhooks", exc_info=True)

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
    ) -> dict[int, UUID]:
        """Resolve one data source per series type, using the ranking sleep and summaries use."""
        return self.crud.winning_source_by_series_type(
            db_session,
            params,
            types,
            user_id,
            self.provider_priority_repo.get_priority_order(db_session),
            self.device_type_priority_repo.get_priority_order(db_session),
        )

    def _aggregated_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        source_by_type: dict[int, UUID] | None = None,
    ) -> PaginatedResponse[TimeSeriesSample]:
        """Downsampled variant of :meth:`get_timeseries`.

        total_count stays unset: counting buckets would scan the whole requested range, which
        is the work the bucket cap exists to avoid.
        """
        rows, truncated = self.crud.get_aggregated_samples(db_session, params, types, user_id, source_by_type)
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
        source_by_type: dict[int, UUID] | None = None,
    ) -> PaginatedResponse[TimeSeriesSample]:
        """Day, week and month values from series_aggregate, the provider's day before ours.

        Weeks start on Monday and months on the 1st, by the local day; a week or month is built from
        its days within the requested range. Pages hold ``limit`` periods; the cursor is a period's
        first day.
        """
        kind = PERIOD_RESOLUTIONS[params.resolution]
        first_day = max(params.start_datetime.date(), _NO_START) if params.start_datetime else _NO_START
        last_day = (
            min((params.end_datetime - timedelta(microseconds=1)).date(), _NO_END) if params.end_datetime else _NO_END
        )
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
        # Our rollup reaches only the days written since it runs: the others come from the samples.
        from_samples = True

        def edge_day(first: date, last: date, latest: bool, starts: Any = None) -> date | None:
            """The outermost day holding a row, or with ``from_samples`` a sample."""
            days = [repo.edge_day(db_session, user_id, params, types, first, last, source_by_type, latest, starts)]
            if from_samples:
                days.append(
                    repo.sample_edge_day(db_session, user_id, params, types, first, last, source_by_type, latest)
                )
            days = [day for day in days if day is not None]
            return (max(days) if latest else min(days)) if days else None

        edges = repo.edge_rows(db_session, user_id, params, types, first_day, last_day, source_by_type, backward)
        if not edges and not from_samples:
            return _page(data=[], params=params, has_more=False, next_cursor=None, previous_cursor=None)
        # A period is up to two rows (the provider's and ours) a day for every series of every source holding
        # data here; with all of them asked for, a page of `limit` periods could be hundreds of thousands of rows.
        days_per_period = {PeriodKind.DAY: 1, PeriodKind.WEEK: 7, PeriodKind.MONTH: 31}[kind]
        limit = max(1, min(params.limit or 50, _PERIOD_ROWS_PER_PAGE // (2 * max(len(edges), 1) * days_per_period)))
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
        rows = repo.day_rows_or_samples(db_session, user_id, types, *window, from_samples, params, source_by_type)

        groups: dict[tuple[date, UUID, int], list[SeriesAggregate | SampleDay]] = defaultdict(list)
        for row, day in rows:
            groups[(_period_of(day, kind), row.data_source_id, row.series_type_definition_id)].append(row)
        periods = sorted({period for period, _, _ in groups})
        overflow = len(periods) > limit
        periods = periods[-limit:] if backward else periods[:limit]
        rest = (first_day, window[0] - timedelta(days=1)) if backward else (window[1] + timedelta(days=1), last_day)
        has_more = overflow or (rest[0] <= rest[1] and edge_day(*rest, False) is not None)

        sources = self.crud._sources_by_id(db_session, {source_id for _, source_id, _ in groups})
        shown = set(periods)
        data = []
        for (period, source_id, type_id), period_rows in sorted(groups.items(), key=lambda item: item[0]):
            if period not in shown:
                continue
            zone_offset = period_rows[0].zone_offset
            stats = _combine(period_rows)
            data.append(
                _to_sample(
                    CalendarPeriod.of_date(period, zone_offset).start,
                    zone_offset,
                    type_id,
                    Decimal(str(_value_of(stats, get_series_type_from_id(type_id)))),
                    None,
                    sources[source_id],
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

    @handle_exceptions
    def get_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
        filter_by_priority: bool = False,
    ) -> PaginatedResponse[TimeSeriesSample]:
        if params.resolution in PERIOD_RESOLUTIONS:
            # An open end stays an open end: the day bounds a read computes around a far date must still be dates.
            params = params.model_copy(
                update={
                    "start_datetime": _clamp(params.start_datetime, _NO_START, _NO_END),
                    "end_datetime": _clamp(params.end_datetime, _NO_START, _NO_END),
                }
            )
        source_by_type = self._winning_sources(db_session, user_id, types, params) if filter_by_priority else None
        if params.resolution in PERIOD_RESOLUTIONS:
            return self._period_timeseries(db_session, user_id, types, params, source_by_type)
        if params.resolution is not Resolution.RAW:
            return self._aggregated_timeseries(db_session, user_id, types, params, source_by_type)

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


timeseries_service = TimeSeriesService(log=getLogger(__name__))
