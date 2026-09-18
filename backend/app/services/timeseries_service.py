import threading
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from sqlalchemy import event as sa_event

from app.database import DbSession
from app.models import DataPointSeries, DataSource
from app.repositories import DataPointSeriesRepository
from app.repositories.data_point_series_repository import AggregatedSample, WriteCounts
from app.schemas.enums import (
    Resolution,
    SeriesType,
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
from app.services.priority_service import priority_service
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_bucket_cursor, encode_cursor


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
) -> TimeSeriesSample:
    series_type = get_series_type_from_id(series_type_definition_id)
    source = None
    if data_source is not None:
        source = SourceMetadata(
            provider=data_source.provider or "unknown",
            source=data_source.source,
            device=data_source.device_model,
            device_type=data_source.device_type,
        )
    return TimeSeriesSample(
        timestamp=timestamp,
        zone_offset=zone_offset,
        type=series_type,
        value=float(value),
        unit=get_series_type_unit(series_type),
        source=source,
        is_daily_total=is_daily_total,
    )


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

    def has_samples_in_range(
        self,
        db_session: DbSession,
        user_id: UUID,
        source: str,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> bool:
        """Whether any sample from `source` already exists for the user in [start, end)."""
        return self.crud.has_samples_in_range(db_session, user_id, source, start_datetime, end_datetime)

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

    def get_approximate_total_count(self, db_session: DbSession) -> int:
        """Get an approximate total count of all data points (planner statistics, no scan)."""
        return self.crud.get_approximate_total_count(db_session)

    def get_approximate_archived_count(self, db_session: DbSession) -> int:
        """Get an approximate count of archived data points (planner statistics, no scan)."""
        return self.crud.get_approximate_archived_count(db_session)

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
            priority_service.priority_repo.get_priority_order(db_session),
            priority_service.device_type_priority_repo.get_priority_order(db_session),
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

        return _page(
            data=[
                _to_sample(
                    s.bucket, s.zone_offset, s.series_type_definition_id, s.value, s.is_daily_total, s.data_source
                )
                for s in samples
            ],
            params=params,
            has_more=has_more,
            next_cursor=encode_bucket_cursor(samples[-1].bucket) if has_next else None,
            previous_cursor=encode_bucket_cursor(samples[0].bucket, "prev") if has_previous else None,
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
        source_by_type = self._winning_sources(db_session, user_id, types, params) if filter_by_priority else None
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
            )
            for sample, data_source in samples
        ]

        return _page(data, params, has_more, next_cursor, previous_cursor, total_count)


timeseries_service = TimeSeriesService(log=getLogger(__name__))
