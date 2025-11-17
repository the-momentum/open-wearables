from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    PrimaryKey,
    FKUser,
    FKWorkout,
    ManyToOne,
    numeric_10_2,
    str_10,
    str_100,
)


class WorkoutStatistic(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    workout_id: Mapped[FKWorkout]

    type: Mapped[str_100]
    value: Mapped[numeric_10_2]
    unit: Mapped[str_10]

    user: Mapped[ManyToOne["User"]]
    workout: Mapped[ManyToOne["Workout"]]
