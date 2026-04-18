import threading
from collections import defaultdict
from datetime import datetime
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from sqlalchemy import event as sa_event

from app.database import DbSession
from app.models import DataPointSeries
from app.repositories import DataPointSeriesRepository
from app.schemas.enums import (
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
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor


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
    ) -> None:
        self.crud.bulk_create(db_session, samples)  # type: ignore[arg-type]
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


timeseries_service = TimeSeriesService(log=getLogger(__name__))
