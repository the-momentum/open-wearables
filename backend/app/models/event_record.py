from uuid import UUID
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, text
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
from app.schemas.enums import EventCategory

if TYPE_CHECKING:
    from app.models.sleep_details import SleepDetails
    from app.models.workout_details import WorkoutDetails
    from app.models.menstrual_cycle_details import MenstrualCycleDetails
    from app.models.meal_details import MealDetails
    from app.models.reproductive_health_details import ReproductiveHealthDetails


# Categories unique by (data source, external_id), not by time: several of their records can
# share one interval, e.g. a flow and a mucus entry logged for the same day.
EXTERNAL_ID_KEYED_CATEGORIES: tuple[EventCategory, ...] = (EventCategory.MEAL, EventCategory.REPRODUCTIVE_HEALTH)
_EXTERNAL_ID_KEYED_LIST = ", ".join(f"'{category}'" for category in EXTERNAL_ID_KEYED_CATEGORIES)
# Partial index predicates, repeated verbatim in ON CONFLICT so Postgres picks the index.
EXTERNAL_ID_KEYED_WHERE = f"category IN ({_EXTERNAL_ID_KEYED_LIST})"
TIME_KEYED_WHERE = f"category NOT IN ({_EXTERNAL_ID_KEYED_LIST})"


class EventRecord(BaseDbModel):
    __tablename__ = "event_record"
    __table_args__ = (
        Index("ix_event_record_source_category", "data_source_id", "category"),
        Index(
            "ix_event_record_source_time",
            "data_source_id",
            "start_datetime",
            "end_datetime",
            unique=True,
            postgresql_where=text(TIME_KEYED_WHERE),
        ),
        Index(
            "ix_event_record_source_external_id",
            "data_source_id",
            "external_id",
            unique=True,
            postgresql_where=text(EXTERNAL_ID_KEYED_WHERE),
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_id: Mapped[str_100 | None]
    data_source_id: Mapped[FKDataSource]

    category: Mapped[str_32]
    type: Mapped[str_32 | None]
    source_name: Mapped[str_64]

    # The whole start-to-end span; for sleep, awake time included (time asleep is in SleepDetails).
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
    meal_detail: Mapped["MealDetails | None"] = relationship(
        "MealDetails",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[MealDetails.record_id]",
    )
    reproductive_health_detail: Mapped["ReproductiveHealthDetails | None"] = relationship(
        "ReproductiveHealthDetails",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[ReproductiveHealthDetails.record_id]",
    )

    @classmethod
    def detail_relationship(cls, category: EventCategory | None) -> list[QueryableAttribute]:
        return {
            EventCategory.SLEEP: [cls.sleep_detail],
            EventCategory.WORKOUT: [cls.workout_detail],
            EventCategory.MENSTRUAL_CYCLE: [cls.menstrual_cycle_detail],
            EventCategory.MEAL: [cls.meal_detail],
            EventCategory.REPRODUCTIVE_HEALTH: [cls.reproductive_health_detail],
        }.get(
            category,
            [
                cls.sleep_detail,
                cls.workout_detail,
                cls.menstrual_cycle_detail,
                cls.meal_detail,
                cls.reproductive_health_detail,
            ],
        )
