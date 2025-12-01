from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, PrimaryKey, Unique, datetime_tz, str_100, str_255, email


class User(BaseDbModel):
    """Data owner model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]

    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
    email: Mapped[email | None]

    external_user_id: Mapped[Unique[str_255] | None]

    workouts: Mapped[OneToMany["Workout"]]
    workout_statistics: Mapped[OneToMany["WorkoutStatistic"]]