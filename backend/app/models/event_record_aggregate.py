from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKEventRecordRef, FKSeriesTypeDefinition, PrimaryKey, numeric_unbounded
from app.schemas.enums import ComputedBy


class EventRecordAggregate(BaseDbModel):
    """Statistics of one series over one event record (a sleep, a workout), one row per computed_by."""

    __tablename__ = "event_record_aggregate"
    __table_args__ = (
        UniqueConstraint(
            "record_id",
            "series_type_definition_id",
            "computed_by",
            name="uq_event_record_aggregate_record_type_computed_by",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    record_id: Mapped[FKEventRecordRef]
    series_type_definition_id: Mapped[FKSeriesTypeDefinition]
    computed_by: Mapped[ComputedBy]
    sum: Mapped[numeric_unbounded | None]
    avg: Mapped[numeric_unbounded | None]
    min: Mapped[numeric_unbounded | None]
    max: Mapped[numeric_unbounded | None]
    last: Mapped[numeric_unbounded | None]
    count: Mapped[int]
