from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import CreatedAt, UpdatedAt, UUIDPrimaryKey


class Session(BaseDbModel):
    __tablename__ = "sessions"

    id: Mapped[UUIDPrimaryKey]
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    conversation: Mapped["Conversation"] = relationship(back_populates="sessions")  # type: ignore[name-defined]
    messages: Mapped[list["Message"]] = relationship(  # type: ignore[name-defined]
        back_populates="session", passive_deletes=True
    )
