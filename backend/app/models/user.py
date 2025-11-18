# ruff: noqa: F821

from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, PrimaryKey, datetime_tz


class User(BaseDbModel):
    """Data owner model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]

    workouts: Mapped[OneToMany["Workout"]]
    heart_rate_data: Mapped[OneToMany["HeartRateData"]]
    heart_rate_recovery: Mapped[OneToMany["HeartRateRecovery"]]
    active_energy: Mapped[OneToMany["ActiveEnergy"]]
