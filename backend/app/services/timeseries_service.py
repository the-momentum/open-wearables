from datetime import datetime
from logging import Logger, getLogger
from typing import TypeVar
from uuid import UUID

from app.database import DbSession
from app.models import DataPointSeries, ExternalDeviceMapping
from app.repositories import DataPointSeriesRepository
from app.schemas import (
    BloodGlucoseSample,
    HeartRateSample,
    HeartRateSampleCreate,
    HeartRateSampleResponse,
    HrvSample,
    Spo2Sample,
    StepSampleCreate,
    StepSampleResponse,
    StepsSample,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.common_types import PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.series_types import SeriesType, get_series_type_from_id
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions

ResponseModel = TypeVar("ResponseModel", HeartRateSampleResponse, StepSampleResponse)


class TimeSeriesService(
    AppService[DataPointSeriesRepository, DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Coordinated access to unified device time series samples."""

    HEART_RATE_TYPE = SeriesType.heart_rate
    STEP_TYPE = SeriesType.steps

    def __init__(self, log: Logger):
        super().__init__(crud_model=DataPointSeriesRepository, model=DataPointSeries, log=log)

    def _build_response(
        self,
        sample: DataPointSeries,
        mapping: ExternalDeviceMapping,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        # Handle new fields if they exist in the model and response schema
        extra_fields = {}
        if hasattr(sample, "context") and hasattr(response_model, "context"):
            extra_fields["context"] = sample.context
        if hasattr(sample, "metadata_") and hasattr(response_model, "metadata"):
            extra_fields["metadata"] = sample.metadata_

        return response_model(
            id=sample.id,
            recorded_at=sample.recorded_at,
            value=sample.value,
            series_type=get_series_type_from_id(sample.series_type_definition_id),
            external_id=sample.external_id,
            external_device_mapping_id=sample.external_device_mapping_id,
            user_id=mapping.user_id,
            provider_name=mapping.provider_name,
            device_id=mapping.device_id,
            **extra_fields,
        )

    def bulk_create_samples(
        self,
        db_session: DbSession,
        samples: list[TimeSeriesSampleCreate] | list[HeartRateSampleCreate] | list[StepSampleCreate],
    ) -> None:
        for sample in samples:
            self.crud.create(db_session, sample)

    @handle_exceptions
    async def get_user_heart_rate_series(
        self,
        db_session: DbSession,
        user_id: str,
        params: TimeSeriesQueryParams,
    ) -> list[HeartRateSampleResponse]:
        samples = self.crud.get_samples(db_session, params, self.HEART_RATE_TYPE, UUID(user_id))
        return [self._build_response(sample, mapping, HeartRateSampleResponse) for sample, mapping in samples]

    @handle_exceptions
    async def get_user_step_series(
        self,
        db_session: DbSession,
        user_id: str,
        params: TimeSeriesQueryParams,
    ) -> list[StepSampleResponse]:
        samples = self.crud.get_samples(db_session, params, self.STEP_TYPE, UUID(user_id))
        return [self._build_response(sample, mapping, StepSampleResponse) for sample, mapping in samples]

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
            pagination=Pagination(has_more=False),
            metadata=TimeseriesMetadata(),
        )


timeseries_service = TimeSeriesService(log=getLogger(__name__))
