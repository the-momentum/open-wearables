from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import DataPointSeries
from app.repositories import DataPointSeriesRepository
from app.schemas import (
    BloodGlucoseSample,
    HeartRateSample,
    HeartRateSampleCreate,
    HrvSample,
    Spo2Sample,
    StepSampleCreate,
    StepsSample,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.common_types import PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.series_types import SeriesType
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class TimeSeriesService(
    AppService[DataPointSeriesRepository, DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Coordinated access to unified device time series samples."""

    def __init__(self, log: Logger):
        super().__init__(crud_model=DataPointSeriesRepository, model=DataPointSeries, log=log)

    def bulk_create_samples(
        self,
        db_session: DbSession,
        samples: list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate],
    ) -> None:
        for sample in samples:
            self.crud.create(db_session, sample)

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

    def get_count_by_provider(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by provider."""
        return self.crud.get_count_by_provider(db_session)

    @handle_exceptions
    async def get_timeseries(
        self,
        db_session: DbSession,
        user_id: UUID,
        type: SeriesType,
        params: TimeSeriesQueryParams,
    ) -> PaginatedResponse[HeartRateSample | HrvSample | Spo2Sample | BloodGlucoseSample | StepsSample]:
        samples = self.crud.get_samples(db_session, params, type, user_id)

        limit = params.limit or 50
        has_more = len(samples) > limit
        next_cursor = None

        if has_more:
            # Get the last item of the current page to form the cursor for the next page
            last_item_in_page = samples[limit - 1][0]
            next_cursor = f"{last_item_in_page.recorded_at.isoformat()}|{last_item_in_page.id}"
            samples = samples[:limit]

        data = []
        for sample, mapping in samples:
            if type == SeriesType.heart_rate:
                item = HeartRateSample(timestamp=sample.recorded_at, bpm=int(sample.value))
            elif type == SeriesType.heart_rate_variability_sdnn:
                item = HrvSample(timestamp=sample.recorded_at, sdnn_ms=float(sample.value))
            elif type == SeriesType.oxygen_saturation:
                item = Spo2Sample(timestamp=sample.recorded_at, percent=float(sample.value))
            elif type == SeriesType.blood_glucose:
                item = BloodGlucoseSample(timestamp=sample.recorded_at, value_mg_dl=float(sample.value))
            elif type == SeriesType.steps:
                item = StepsSample(
                    timestamp=sample.recorded_at,
                    count=int(sample.value),
                    duration_seconds=None,
                )
            else:
                continue
            data.append(item)

        return PaginatedResponse(
            data=data,
            pagination=Pagination(has_more=has_more, next_cursor=next_cursor),
            metadata=TimeseriesMetadata(
                sample_count=len(data),
                start_time=params.start_datetime,
                end_time=params.end_datetime,
            ),
        )


timeseries_service = TimeSeriesService(log=getLogger(__name__))
