from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession
    from app.models.message import Message

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import CreatedAt, UUIDPrimaryKey


class Conversation(BaseDbModel):
    __tablename__ = "conversations"

    id: Mapped[UUIDPrimaryKey]
    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    created_at: Mapped[CreatedAt]

    session: Mapped["ChatSession | None"] = relationship(back_populates="conversation")  # type: ignore[name-defined]
    messages: Mapped[list["Message"]] = relationship(  # type: ignore[name-defined]
        back_populates="conversation", cascade="all, delete-orphan"
    )
