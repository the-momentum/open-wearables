from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    ManyToOne,
    OneToMany,
    PrimaryKey,
    datetime_tz,
    numeric_10_3,
    str_100,
)


class Workout(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    provider_id: Mapped[str_100 | None] = None
    user_id: Mapped[FKUser]

    type: Mapped[str_100 | None] = None
    duration_seconds: Mapped[numeric_10_3]
    source_name: Mapped[str_100]

    start_datetime: Mapped[datetime_tz]
    end_datetime: Mapped[datetime_tz]

    user: Mapped[ManyToOne["User"]]

    statistics: Mapped[OneToMany["WorkoutStatistic"]]