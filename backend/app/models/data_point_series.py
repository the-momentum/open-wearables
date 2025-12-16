from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKExternalMapping, FKSeriesTypeDefinition, PrimaryKey, datetime_tz, numeric_10_3


class DataPointSeries(BaseDbModel):
    """Unified time-series data points for device metrics (heart rate, steps, energy, etc.)."""

    __tablename__ = "data_point_series"
    __table_args__ = (
        Index("idx_data_point_series_mapping_type_time", "external_mapping_id", "series_type_id", "recorded_at"),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_mapping_id: Mapped[FKExternalMapping]
    recorded_at: Mapped[datetime_tz]
    value: Mapped[numeric_10_3]
    series_type_id: Mapped[FKSeriesTypeDefinition]
