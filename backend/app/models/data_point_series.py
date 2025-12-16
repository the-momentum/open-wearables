from uuid import UUID

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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
    
    # New fields for Taxonomy v2
    context: Mapped[str | None] = mapped_column(String(32))
    metadata_: Mapped[dict | None] = mapped_column(JSONB)  # 'metadata' is reserved in SQLAlchemy models sometimes
