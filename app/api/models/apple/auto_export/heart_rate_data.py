from sqlalchemy.orm import Mapped
from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    FKWorkout,
    ManyToOne,
    PrimaryKey,
    datetime_tz,
    numeric_10_3,
    str_50,
)

class HeartRateData(BaseDbModel):
    id: Mapped[PrimaryKey[int]]
    user_id: Mapped[FKUser]
    workout_id: Mapped[FKWorkout]
    date: Mapped[datetime_tz]
    source: Mapped[str | None]
    units: Mapped[str_50 | None]
    avg: Mapped[numeric_10_3 | None]
    min: Mapped[numeric_10_3 | None]
    max: Mapped[numeric_10_3 | None]

    user: Mapped[ManyToOne["User"]]
    workout: Mapped[ManyToOne["Workout"]]