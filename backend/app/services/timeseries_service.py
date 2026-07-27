import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import event as sa_event

from app.database import DbSession
from app.models import DataPointSeries, DataSource
from app.repositories import DataPointSeriesRepository
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.enums import (
    RESOLUTION_BUCKET_SECONDS,
    RESOLUTION_MAX_RANGE_DAYS,
    AggregationMethod,
    SeriesType,
    TimeseriesResolution,
    get_aggregation_method,
    get_series_type_from_id,
    get_series_type_unit,
)
from app.schemas.model_crud.activities import (
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.responses.activity import TimeSeriesSample
from app.schemas.utils import (
    PaginatedResponse,
    Pagination,
    SourceMetadata,
    TimeseriesMetadata,
)
from app.services.outgoing_webhooks import svix as svix_service
from app.services.outgoing_webhooks.events import on_timeseries_batch_saved
from app.services.services import AppService
from app.utils.exceptions import TimeseriesRangeTooLargeError, handle_exceptions
from app.utils.pagination import decode_cursor, encode_cursor


class _SampleBucket(NamedTuple):
    """One downsampled time bucket, ready to be mapped to a response item."""

    timestamp: datetime  # UTC-aligned bucket start
    sample_id: UUID  # id of the latest raw sample in the bucket (cursor tiebreaker)
    series_type: SeriesType
    value: float
    zone_offset: str | None
    data_source: DataSource | None


class TimeSeriesService(
    AppService[
        DataPointSeriesRepository,
        DataPointSeries,
        TimeSeriesSampleCreate,
        TimeSeriesSampleUpdate,
    ],
):
    """Coordinated access to unified device time series samples."""

    def __init__(self, log: Logger):
        super().__init__(crud_model=DataPointSeriesRepository, model=DataPointSeries, log=log)

    def bulk_create_samples(
        self,
        db_session: DbSession,
        samples: (list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate]),
    ) -> WriteCounts:
        counts = self.crud.bulk_create(db_session, samples)  # ty:ignore[invalid-argument-type]
        samples_copy = list(samples)

        @sa_event.listens_for(db_session, "after_commit", once=True)
        def _start_webhook_thread(session: DbSession) -> None:  # noqa: ARG001
            if not svix_service.is_enabled():
                return
            threading.Thread(
                target=self._emit_timeseries_webhooks,
                args=(samples_copy,),
                daemon=True,
            ).start()

        return counts

    @staticmethod
    def _emit_timeseries_webhooks(
        samples: list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate],
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
                )
        except Exception:
            getLogger(__name__).warning("Failed to emit timeseries webhooks", exc_info=True)

    def get_total_count(self, db_session: DbSession) -> int:
        """Get total count of all data points."""
        return self.crud.get_total_count(db_session)

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

    def get_count_by_series_type(self, db_session: DbSession) -> list[tuple[int, int]]:
        """Get count of data points grouped by series type ID."""
        return self.crud.get_count_by_series_type(db_session)

    def get_count_by_source(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by source."""
        return self.crud.get_count_by_source(db_session)

    @handle_exceptions
    def get_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
    ) -> PaginatedResponse[TimeSeriesSample]:
        if params.resolution is not TimeseriesResolution.RAW:
            return self._get_downsampled_timeseries(db_session, user_id, types, params)

        samples, total_count = self.crud.get_samples(db_session, params, types, user_id)

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

        # Map to response format
        data = []
        for sample, data_source in samples:
            series_type = get_series_type_from_id(sample.series_type_definition_id)
            unit = get_series_type_unit(series_type)

            # Build source from data source info if available
            source = None
            if data_source:
                source = SourceMetadata(
                    provider=data_source.source or "unknown",
                    device=data_source.device_model,
                )

            item = TimeSeriesSample(
                timestamp=sample.recorded_at,
                zone_offset=sample.zone_offset,
                type=series_type,
                value=float(sample.value),
                unit=unit,
                source=source,
                is_daily_total=sample.is_daily_total,
            )
            data.append(item)

        return PaginatedResponse(
            data=data,
            pagination=Pagination(
                has_more=has_more,
                next_cursor=next_cursor,
                previous_cursor=previous_cursor,
                total_count=total_count,
            ),
            metadata=TimeseriesMetadata(
                sample_count=len(data),
                start_time=params.start_datetime,
                end_time=params.end_datetime,
            ),
        )

    def _get_downsampled_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        types: list[SeriesType],
        params: TimeSeriesQueryParams,
    ) -> PaginatedResponse[TimeSeriesSample]:
        """Downsample raw samples into fixed time buckets before paginating.

        Bucketing happens over the full requested range (no raw-level pagination),
        so a bucket can never be split across pages. The aggregation function is
        chosen per series type via ``get_aggregation_method`` — the same mapping
        the daily archive rollup uses: SUM for cumulative metrics (steps,
        distance, energy), AVG for rate/level metrics (heart rate, temperature),
        MAX for peak metrics.
        """
        self._validate_downsampled_range(params)
        interval_seconds = RESOLUTION_BUCKET_SECONDS[params.resolution]
        rows = self.crud.get_samples_for_range(db_session, params, types, user_id)
        buckets = self._bucket_samples(rows, interval_seconds)

        limit = params.limit or 50
        is_backward = params.cursor and params.cursor.startswith("prev_")

        # Total matching buckets, calculated BEFORE cursor pagination (as the
        # raw path does for raw samples)
        total_count = len(buckets)

        # Keyset pagination over the buckets, mirroring the raw path semantics
        if params.cursor:
            cursor_ts, cursor_id, direction = decode_cursor(params.cursor)
            if direction == "prev":
                buckets = [b for b in buckets if (b.timestamp, b.sample_id) < (cursor_ts, cursor_id)]
            else:
                buckets = [b for b in buckets if (b.timestamp, b.sample_id) > (cursor_ts, cursor_id)]

        has_more = len(buckets) > limit
        if has_more:
            buckets = buckets[-limit:] if is_backward else buckets[:limit]

        next_cursor = None
        previous_cursor = None
        if buckets:
            if has_more:
                next_cursor = encode_cursor(buckets[-1].timestamp, buckets[-1].sample_id, "next")
            if params.cursor:
                if is_backward:
                    if has_more:
                        previous_cursor = encode_cursor(buckets[0].timestamp, buckets[0].sample_id, "prev")
                else:
                    previous_cursor = encode_cursor(buckets[0].timestamp, buckets[0].sample_id, "prev")

        data = []
        for bucket in buckets:
            source = None
            if bucket.data_source:
                source = SourceMetadata(
                    provider=bucket.data_source.source or "unknown",
                    device=bucket.data_source.device_model,
                )
            data.append(
                TimeSeriesSample(
                    timestamp=bucket.timestamp,
                    zone_offset=bucket.zone_offset,
                    type=bucket.series_type,
                    value=bucket.value,
                    unit=get_series_type_unit(bucket.series_type),
                    source=source,
                    # A bucket is never a provider-reported daily total
                    is_daily_total=None,
                )
            )

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

    @staticmethod
    def _validate_downsampled_range(params: TimeSeriesQueryParams) -> None:
        """Reject downsampled queries whose span exceeds the resolution's cap.

        Downsampling loads every raw row of the requested range into memory
        before bucketing (no raw-level pagination), so the span must be bounded
        relative to the bucket width — see RESOLUTION_MAX_RANGE_DAYS. Raises
        before any database fetch. Bounds are optional in the query params, so
        a range that cannot be measured (missing bound) is left to the raw path
        conventions and not validated here.
        """
        if params.start_datetime is None or params.end_datetime is None:
            return
        max_days = RESOLUTION_MAX_RANGE_DAYS[params.resolution]
        if params.end_datetime - params.start_datetime > timedelta(days=max_days):
            raise TimeseriesRangeTooLargeError(params.resolution, max_days)

    @staticmethod
    def _bucket_samples(
        rows: list[tuple[DataPointSeries, DataSource]],
        interval_seconds: int,
    ) -> list[_SampleBucket]:
        """Group raw samples into UTC-aligned buckets and aggregate each group.

        Samples are bucketed per (bucket start, series type, data source), so
        two devices reporting the same metric never merge into one value.
        Returns buckets ordered by (timestamp, sample_id) for keyset pagination.
        """
        groups: dict[tuple[int, int, UUID], list[tuple[DataPointSeries, DataSource]]] = defaultdict(list)
        for sample, data_source in rows:
            bucket_start = int(sample.recorded_at.timestamp()) // interval_seconds * interval_seconds
            key = (bucket_start, sample.series_type_definition_id, sample.data_source_id)
            groups[key].append((sample, data_source))

        buckets: list[_SampleBucket] = []
        for (bucket_start, series_type_id, _), members in groups.items():
            series_type = get_series_type_from_id(series_type_id)
            method = get_aggregation_method(series_type)

            if method is AggregationMethod.SUM:
                # Providers can store BOTH a daily-total row (is_daily_total=True)
                # and intraday samples for the same day/series (e.g. Garmin
                # dailies alongside epochs). Summing both would double-count the
                # day, so — mirroring the daily rollup's prefer_daily_sum
                # semantics, where daily-total rows win over intraday samples at
                # daily granularity — sub-day SUM buckets count intraday samples
                # only and drop daily-total rows. None counts as intraday
                # (legacy rows), matching prefer_daily_sum's NULL handling.
                members = [(sample, ds) for sample, ds in members if sample.is_daily_total is not True]
                if not members:
                    # The bucket only held daily-total rows: nothing to report
                    # at sub-day granularity.
                    continue
                value = sum(float(sample.value) for sample, _ in members)
            elif method is AggregationMethod.MAX:
                value = max(float(sample.value) for sample, _ in members)
            else:
                value = sum(float(sample.value) for sample, _ in members) / len(members)

            # Members arrive in chronological order; the last one anchors the
            # bucket's cursor identity and representative zone offset.
            representative, data_source = members[-1]
            buckets.append(
                _SampleBucket(
                    timestamp=datetime.fromtimestamp(bucket_start, tz=timezone.utc),
                    sample_id=representative.id,
                    series_type=series_type,
                    value=value,
                    zone_offset=representative.zone_offset,
                    data_source=data_source,
                )
            )

        buckets.sort(key=lambda b: (b.timestamp, b.sample_id))
        return buckets


timeseries_service = TimeSeriesService(log=getLogger(__name__))
