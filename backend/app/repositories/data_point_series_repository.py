from uuid import UUID

from sqlalchemy import desc

from app.constants.series_types import get_series_type_id
from app.database import DbSession
from app.models import DataPointSeries, ExternalDeviceMapping
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.repositories.repositories import CrudRepository
from app.schemas import SeriesType, TimeSeriesQueryParams, TimeSeriesSampleCreate, TimeSeriesSampleUpdate


class DataPointSeriesRepository(
    CrudRepository[DataPointSeries, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Repository for unified device data point series."""

    def __init__(self, model: type[DataPointSeries]):
        super().__init__(model)
        self.mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)

    def create(self, db_session: DbSession, creator: TimeSeriesSampleCreate) -> DataPointSeries:
        mapping = self.mapping_repo.ensure_mapping(
            db_session,
            creator.user_id,
            creator.provider_id,
            creator.device_id,
            creator.external_mapping_id,
        )

        creation_data = creator.model_dump()
        creation_data["external_mapping_id"] = mapping.id
        creation_data["series_type_id"] = get_series_type_id(creator.series_type)
        for redundant_key in ("user_id", "provider_id", "device_id", "external_mapping_id", "series_type"):
            creation_data.pop(redundant_key, None)

        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def get_samples(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        series_type: SeriesType,
        user_id: UUID,
    ) -> list[tuple[DataPointSeries, ExternalDeviceMapping]]:
        query = (
            db_session.query(self.model, ExternalDeviceMapping)
            .join(
                ExternalDeviceMapping,
                self.model.external_mapping_id == ExternalDeviceMapping.id,
            )
            .filter(self.model.series_type_id == get_series_type_id(series_type))
            .filter(ExternalDeviceMapping.user_id == user_id)
        )

        if params.external_mapping_id:
            query = query.filter(self.model.external_mapping_id == params.external_mapping_id)
        elif params.device_id:
            query = query.filter(ExternalDeviceMapping.device_id == params.device_id)
        else:
            # Require at least one device-level discriminator to avoid scanning entire dataset
            return []

        if getattr(params, "provider_id", None):
            query = query.filter(ExternalDeviceMapping.provider_id == params.provider_id)

        if params.start_datetime:
            query = query.filter(self.model.recorded_at >= params.start_datetime)

        if params.end_datetime:
            query = query.filter(self.model.recorded_at <= params.end_datetime)

        return query.order_by(desc(self.model.recorded_at)).limit(1000).all()
