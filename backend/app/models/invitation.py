from uuid import UUID

from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import FKDeveloper, ManyToOne, PrimaryKey, UniqueIndex, datetime_tz, str_50, str_255
from app.models import Developer


class Invitation(BaseDbModel):
    """Invitation to join the team as a developer."""

    id: Mapped[PrimaryKey[UUID]]
    email: Mapped[str_255]
    token: Mapped[UniqueIndex[str_255]]
    status: Mapped[str_50]  # pending, sent, accepted, expired, revoked
    expires_at: Mapped[datetime_tz]
    created_at: Mapped[datetime_tz]

    invited_by_id: Mapped[FKDeveloper | None]
    invited_by: Mapped[ManyToOne["Developer"] | None] = relationship(
        "Developer",
        foreign_keys="[Invitation.invited_by_id]",
        lazy="joined",
    )

