from uuid import UUID


from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, Unique, date_col, bool_col, str_64

class PersonalRecord(BaseDbModel):
    """Slow-changing physical attributes linked to a user."""

    __tablename__ = "personal_record"

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[Unique[FKUser]]

    birth_date: Mapped[date_col | None]
    sex: Mapped[bool_col | None]
    gender: Mapped[str_64 | None]

    user: Mapped["User"] = relationship(back_populates="personal_record")

