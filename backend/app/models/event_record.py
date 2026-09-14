from uuid import UUID
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, QueryableAttribute, relationship

from app.database import BaseDbModel
from app.mappings import (
    FKDataSource,
    PrimaryKey,
    str_10,
    str_32,
    str_64,
    str_100,
)

if TYPE_CHECKING:
    from app.models.sleep_details import SleepDetails
    from app.models.workout_details import WorkoutDetails
    from app.models.menstrual_cycle_details import MenstrualCycleDetails


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

    sleep_detail: Mapped["SleepDetails | None"] = relationship(
        "SleepDetails",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[SleepDetails.record_id]",
    )
    workout_detail: Mapped["WorkoutDetails | None"] = relationship(
        "WorkoutDetails",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[WorkoutDetails.record_id]",
    )
    menstrual_cycle_detail: Mapped["MenstrualCycleDetails | None"] = relationship(
        "MenstrualCycleDetails",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[MenstrualCycleDetails.record_id]",
    )

    @classmethod
    def detail_relationship(cls, category: str | None) -> list[QueryableAttribute]:
        return {
            "sleep": [cls.sleep_detail],
            "workout": [cls.workout_detail],
            "menstrual_cycle": [cls.menstrual_cycle_detail],
        }.get(category or "", [cls.sleep_detail, cls.workout_detail, cls.menstrual_cycle_detail])
