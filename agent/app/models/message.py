from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.chat_session import Session
    from app.models.conversation import Conversation

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import CreatedAt, UUIDPrimaryKey
from app.schemas.agent import MessageRole


class Message(BaseDbModel):
    __tablename__ = "messages"

    id: Mapped[UUIDPrimaryKey]
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[CreatedAt]

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")  # type: ignore[name-defined]
    session: Mapped["Session | None"] = relationship(back_populates="messages")  # type: ignore[name-defined]
