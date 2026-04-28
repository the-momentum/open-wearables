from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.chat_session import Session
    from app.models.message import Message

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import CreatedAt, UpdatedAt, UUIDPrimaryKey
from app.schemas.agent import ConversationStatus


class Conversation(BaseDbModel):
    __tablename__ = "conversations"

    id: Mapped[UUIDPrimaryKey]
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=ConversationStatus.ACTIVE,
        server_default=ConversationStatus.ACTIVE.value,
    )
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    agent_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    sessions: Mapped[list["Session"]] = relationship(  # type: ignore[name-defined]
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(  # type: ignore[name-defined]
        back_populates="conversation", cascade="all, delete-orphan"
    )
