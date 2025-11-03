from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    FKWorkout,
    ManyToOne,
    PrimaryKey,
    datetime_tz,
    numeric_15_5,
    str_50,
)

class ActiveEnergy(BaseDbModel):
    id: Mapped[PrimaryKey[int]]
    user_id: Mapped[FKUser]
    workout_id: Mapped[FKWorkout]
    date: Mapped[datetime_tz]
    source: Mapped[str | None]
    units: Mapped[str_50 | None]
    qty: Mapped[numeric_15_5 | None]

    user: Mapped[ManyToOne["User"]]
    workout: Mapped[ManyToOne["Workout"]]