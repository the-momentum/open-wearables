from uuid import UUID
from datetime import datetime

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, email, str_100, str_255


class User(BaseDbModel):
    """Data owner model"""

    # Seed users are a handful at most, so the partial index stays tiny and lets
    # telemetry exclude them without scanning the whole table.
    __table_args__ = (Index("ix_user_is_seed", "id", postgresql_where=text("is_seed")),)

    id: Mapped[PrimaryKey[UUID]]

    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
    email: Mapped[email | None]

    external_user_id: Mapped[Unique[str_255] | None]

    # Synthetic user created by the seed data generator, excluded from telemetry counts
    is_seed: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    personal_record: Mapped["PersonalRecord | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
