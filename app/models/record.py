from uuid import UUID
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    PrimaryKey,
    FKUser,
    ManyToOne,
    OneToMany,
    datetime_tz,
    numeric_15_5,
    str_10,
    str_100,
    str_50,
)


class Record(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    provider_id: Mapped[UUID | None] = None
    user_id: Mapped[FKUser]

    type: Mapped[str_50 | None] = None
    sourceName: Mapped[str_100]
    startDate: Mapped[datetime_tz]
    endDate: Mapped[datetime_tz]
    unit: Mapped[str_10]
    value: Mapped[numeric_15_5]

    user: Mapped[ManyToOne["User"]]
    metadataEntries: Mapped[OneToMany["MetadataEntry"]]
