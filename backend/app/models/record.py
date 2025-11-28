from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    ManyToOne,
    OneToMany,
    PrimaryKey,
    datetime_tz,
    numeric_15_5,
    str_10,
    str_100,
)


class Record(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    provider_id: Mapped[UUID | None] = None
    user_id: Mapped[FKUser]

    type: Mapped[str_100 | None] = None
    sourceName: Mapped[str_100]
    startDate: Mapped[datetime_tz]
    endDate: Mapped[datetime_tz]
    unit: Mapped[str_10]
    value: Mapped[numeric_15_5]

    user: Mapped[ManyToOne["User"]]
    metadataEntries: Mapped[OneToMany["MetadataEntry"]]
