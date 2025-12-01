from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz, str_255


class Developer(BaseDbModel):
    """Admin of the portal model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]

    email: Mapped[Unique[str_255]]
    hashed_password: Mapped[str_255]
