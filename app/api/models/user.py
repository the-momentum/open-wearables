from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, PrimaryKey, Unique, UniqueIndex, datetime_tz, email


class User(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    auth0_id: Mapped[Unique[str]]
    email: Mapped[Unique[email]]
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]

    workouts: Mapped[OneToMany["Workout"]]
    heart_rate_data: Mapped[OneToMany["HeartRateData"]]
    heart_rate_recovery: Mapped[OneToMany["HeartRateRecovery"]]
    active_energy: Mapped[OneToMany["ActiveEnergy"]]
