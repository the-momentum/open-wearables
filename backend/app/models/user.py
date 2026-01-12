from uuid import UUID

from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz, email, str_100, str_255


class User(BaseDbModel):
    """Data owner model"""

    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]

    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
    email: Mapped[email | None]

    external_user_id: Mapped[Unique[str_255] | None]

    personal_record: Mapped["PersonalRecord | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
