from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import (
    FKUser,
    FKRecord,
    ManyToOne,
    PrimaryKey,
    numeric_15_5,
    str_50,
)


class MetadataEntry(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    record_id: Mapped[FKRecord]

    key: Mapped[str_50]
    value: Mapped[numeric_15_5]

    user: Mapped[ManyToOne["User"]]
    record: Mapped[ManyToOne["Record"]]
