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
    str_255,
    str_2000,
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

    # Human-readable metadata forwarded from third-party providers via the
    # Apple HealthKit and Health Connect SDKs. ``title`` is the workout
    # display name (e.g. ``"45 min Power Zone Endurance Ride"``); ``notes``
    # is a longer free-form description. Both are optional because many
    # providers don't populate them.
    title: Mapped[str_255 | None]
    notes: Mapped[str_2000 | None]

    duration_seconds: Mapped[int | None]

    start_datetime: Mapped[datetime]
    end_datetime: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]

    detail: Mapped["EventRecordDetail | None"] = relationship(
        "EventRecordDetail",
        uselist=False,
        cascade="all, delete-orphan",
    )
