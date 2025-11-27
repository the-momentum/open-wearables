from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, PrimaryKey, datetime_tz, str_100, str_255, email


class User(BaseDbModel):
    """Data owner model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]

    # Optional user information fields
    first_name: Mapped[Optional[str_100]] = None
    last_name: Mapped[Optional[str_100]] = None
    email: Mapped[Optional[email]] = None
    client_user_id: Mapped[str_255]

    workouts: Mapped[OneToMany["Workout"]]
    heart_rate_data: Mapped[OneToMany["HeartRateData"]]
    heart_rate_recovery: Mapped[OneToMany["HeartRateRecovery"]]
    active_energy: Mapped[OneToMany["ActiveEnergy"]]
