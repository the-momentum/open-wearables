from uuid import UUID
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKDataSource,
    FKSeriesTypeDefinition,
    PrimaryKey,
    numeric_10_3,
    str_10,
    str_100,
)


class DataPointSeries(BaseDbModel):
    """Unified time-series data points for device metrics (heart rate, steps, energy, etc.)."""

    __tablename__ = "data_point_series"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id",
            "series_type_definition_id",
            "recorded_at",
            name="uq_data_point_series_source_type_time",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_id: Mapped[str_100 | None]
    data_source_id: Mapped[FKDataSource]
    recorded_at: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]
    value: Mapped[numeric_10_3]
    series_type_definition_id: Mapped[FKSeriesTypeDefinition]
