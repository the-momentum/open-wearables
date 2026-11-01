from datetime import datetime

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import Unique, email, str_100, str_255


class User(BaseDbModel):
    """Data owner model.

    ``id`` is the Firebase UID of the corresponding row in the Ren database, supplied
    by the caller of ``POST /users`` rather than generated here. The two databases hold
    a strict one-to-one mirror of the same user population keyed on the same id, so
    nothing may mint a user id locally.
    """

    __table_args__ = (Index("ix_user_is_seed", "id", postgresql_where=text("is_seed")),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
    email: Mapped[email | None]

    external_user_id: Mapped[Unique[str_255] | None]

    # Synthetic user created by the seed data generator
    is_seed: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    personal_record: Mapped["PersonalRecord | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
