from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, str_100, str_255


class Developer(BaseDbModel):
    """Admin of the portal model"""

    id: Mapped[PrimaryKey[UUID]]
    updated_at: Mapped[datetime]

    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
    email: Mapped[Unique[str_255]]
    hashed_password: Mapped[str_255]
