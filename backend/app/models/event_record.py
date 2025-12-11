from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import (
    FKExternalMapping,
    PrimaryKey,
    datetime_tz,
    str_32,
    str_64,
    str_100,
)


class EventRecord(BaseDbModel):
    __tablename__ = "event_record"
    __table_args__ = (
        Index("idx_event_record_mapping_category", "external_mapping_id", "category"),
        Index("idx_event_record_mapping_time", "external_mapping_id", "start_datetime", "end_datetime"),
        UniqueConstraint(
            "external_mapping_id",
            "start_datetime",
            "category",
            name="uq_event_record_datetime_category",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_id: Mapped[str_100 | None]
    external_device_mapping: Mapped[FKExternalMapping]

    category: Mapped[str_32]
    type: Mapped[str_32 | None]
    source_name: Mapped[str_64]

    duration_seconds: Mapped[int | None]

    start_datetime: Mapped[datetime_tz]
    end_datetime: Mapped[datetime_tz]

    detail: Mapped["EventRecordDetail | None"] = relationship(
        "EventRecordDetail",
        uselist=False,
        cascade="all, delete-orphan",
    )
