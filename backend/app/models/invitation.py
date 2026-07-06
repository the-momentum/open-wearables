from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import FKDeveloper, ManyToOne, PrimaryKey, Unique, str_255
from app.models import Developer
from app.schemas.model_crud.user_management import InvitationStatus


class Invitation(BaseDbModel):
    """Invitation to join the team as a developer."""

    id: Mapped[PrimaryKey[UUID]]
    email: Mapped[str_255]
    token: Mapped[Unique[str_255]]
    status: Mapped[InvitationStatus]
    expires_at: Mapped[datetime]

    invited_by_id: Mapped[FKDeveloper | None]
    invited_by: Mapped[ManyToOne["Developer"] | None] = relationship(
        "Developer",
        foreign_keys="[Invitation.invited_by_id]",
        lazy="joined",
    )
