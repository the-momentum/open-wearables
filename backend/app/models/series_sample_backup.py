from uuid import UUID
from datetime import datetime

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKDataSource,
    FKSeriesTypeDefinition,
    PrimaryKey,
    numeric_unbounded,
    str_10,
    str_100,
)


class SeriesSampleBackup(BaseDbModel):
    """Day and session values code before the aggregate tables stored as series_sample rows, moved here once the
    aggregate backfill copied them into the aggregate tables. Kept to restore them; nothing reads them."""

    __tablename__ = "series_sample_backup"
    __table_args__ = (
        Index("ix_series_sample_backup_source_type_time", "data_source_id", "series_type_definition_id", "recorded_at"),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_id: Mapped[str_100 | None]
    data_source_id: Mapped[FKDataSource]
    recorded_at: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]
    window_seconds: Mapped[int | None]
    value: Mapped[numeric_unbounded]
    series_type_definition_id: Mapped[FKSeriesTypeDefinition]
    is_daily_total: Mapped[bool | None]
