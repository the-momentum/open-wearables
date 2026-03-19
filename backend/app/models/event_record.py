from uuid import UUID
from datetime import datetime

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import (
    FKDataSource,
    PrimaryKey,
    str_10,
    str_32,
    str_64,
    str_100,
)


class EventRecord(BaseDbModel):
    __tablename__ = "event_record"
    __table_args__ = (
        Index("ix_event_record_source_category", "data_source_id", "category"),
        Index("ix_event_record_source_time", "data_source_id", "start_datetime", "end_datetime", unique=True),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_id: Mapped[str_100 | None]
    data_source_id: Mapped[FKDataSource]

    category: Mapped[str_32]
    type: Mapped[str_32 | None]
    source_name: Mapped[str_64]

    duration_seconds: Mapped[int | None]

    start_datetime: Mapped[datetime]
    end_datetime: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]

    detail: Mapped["EventRecordDetail | None"] = relationship(
        "EventRecordDetail",
        uselist=False,
        cascade="all, delete-orphan",
    )
