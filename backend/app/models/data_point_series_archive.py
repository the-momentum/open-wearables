from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKDataSource,
    FKSeriesTypeDefinition,
    PrimaryKey,
    Indexed,
    date_col,
    numeric_10_3,
)


class DataPointSeriesArchive(BaseDbModel):
    """Daily-aggregated archive of time-series data points.

    Exactly one row per (data_source_id, series_type_definition_id, date).
    The ``value`` column stores the canonical daily aggregate determined by the
    series type's ``AggregationMethod`` (sum/avg/max — see series_types.py).
    """

    __tablename__ = "data_point_series_archive"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id",
            "series_type_definition_id",
            "date",
            name="uq_archive_source_type_date",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    data_source_id: Mapped[FKDataSource]
    series_type_definition_id: Mapped[FKSeriesTypeDefinition]
    date: Mapped[Indexed[date_col]]
    value: Mapped[numeric_10_3]
    sample_count: Mapped[int]
