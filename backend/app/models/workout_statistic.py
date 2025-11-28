from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    FKWorkout,
    ManyToOne,
    PrimaryKey,
    numeric_10_3,
    str_10,
    str_100,
    datetime_tz,
)


class WorkoutStatistic(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    workout_id: Mapped[FKWorkout | None] = None

    type: Mapped[str_100]
    start_datetime: Mapped[datetime_tz]
    end_datetime: Mapped[datetime_tz]
    min: Mapped[numeric_10_3 | None] = None
    max: Mapped[numeric_10_3 | None] = None
    avg: Mapped[numeric_10_3 | None] = None
    unit: Mapped[str_10]

    user: Mapped[ManyToOne["User"]]
    workout: Mapped[ManyToOne["Workout"]]
