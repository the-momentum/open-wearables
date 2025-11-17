from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    ManyToOne,
    OneToMany,
    PrimaryKey,
    datetime_tz,
    numeric_10_2,
    str_10,
    str_100,
    str_50,
)


class Workout(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    provider_id: Mapped[UUID | None] = None
    user_id: Mapped[FKUser]

    type: Mapped[str_50 | None] = None
    duration: Mapped[numeric_10_2]
    durationUnit: Mapped[str_10]
    sourceName: Mapped[str_100]

    startDate: Mapped[datetime_tz]
    endDate: Mapped[datetime_tz]

    user: Mapped[ManyToOne["User"]]

    # np. active_energy, heart_rate_data
    workout_statistics: Mapped[OneToMany["WorkoutStatistic"]]
    heart_rate_data: Mapped[OneToMany["HeartRateData"]]
    heart_rate_recovery: Mapped[OneToMany["HeartRateRecovery"]]
    active_energy: Mapped[OneToMany["ActiveEnergy"]]

    # workout_entries: Mapped[OneToMany["WorkoutEntry"]] ??
    # workout_routes: Mapped[OneToMany["WorkoutRoute"]] ??
