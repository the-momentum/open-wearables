from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDataSource, FKSeriesTypeDefinition, PrimaryKey, numeric_10_3, str_10
from app.schemas.enums import ComputedBy, PeriodKind


class SeriesAggregate(BaseDbModel):
    """Statistics of one series over one calendar period, one row per source and computed_by."""

    __tablename__ = "series_aggregate"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id",
            "series_type_definition_id",
            "period_kind",
            "period_start",
            "computed_by",
            name="uq_series_aggregate_source_type_period_computed_by",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    data_source_id: Mapped[FKDataSource]
    series_type_definition_id: Mapped[FKSeriesTypeDefinition]
    period_kind: Mapped[PeriodKind]
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    zone_offset: Mapped[str_10]
    computed_by: Mapped[ComputedBy]
    sum: Mapped[numeric_10_3 | None]
    avg: Mapped[numeric_10_3 | None]
    min: Mapped[numeric_10_3 | None]
    max: Mapped[numeric_10_3 | None]
    last: Mapped[numeric_10_3 | None]
    count: Mapped[int]
