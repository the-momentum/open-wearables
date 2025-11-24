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
    workout_id: Mapped[FKWorkout]

    type: Mapped[str_100]
    sourceName: Mapped[str_100]
    startDate: Mapped[datetime_tz]
    endDate: Mapped[datetime_tz]
    min: Mapped[numeric_10_3]
    max: Mapped[numeric_10_3]
    avg: Mapped[numeric_10_3]
    unit: Mapped[str_10]

    user: Mapped[ManyToOne["User"]]
    workout: Mapped[ManyToOne["Workout"]]
