from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz, str_100, str_255, email


class Developer(BaseDbModel):
    """Admin of the portal model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]

    username: Mapped[Unique[str_100]]
    hashed_password: Mapped[str_255]
    email: Mapped[Unique[str_255] | None]
