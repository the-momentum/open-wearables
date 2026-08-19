from datetime import date
from uuid import UUID

from sqlalchemy import Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKDataSource, PrimaryKey, numeric_10_3, str_10


class ActivitySummary(BaseDbModel):
    """Apple Health ActivitySummary: daily ring data (Move/Exercise/Stand) with goals."""

    __tablename__ = "activity_summary"
    __table_args__ = (
        UniqueConstraint("data_source_id", "date", name="uq_activity_summary_source_date"),
    )

    id: Mapped[PrimaryKey[UUID]]
    data_source_id: Mapped[FKDataSource]
    date: Mapped[date] = mapped_column(Date, nullable=False)
    active_energy_burned: Mapped[numeric_10_3]
    active_energy_burned_goal: Mapped[numeric_10_3]
    active_energy_burned_unit: Mapped[str_10]
    apple_move_time: Mapped[numeric_10_3]
    apple_move_time_goal: Mapped[numeric_10_3]
    apple_exercise_time: Mapped[numeric_10_3]
    apple_exercise_time_goal: Mapped[numeric_10_3]
    apple_stand_hours: Mapped[numeric_10_3]
    apple_stand_hours_goal: Mapped[numeric_10_3]
