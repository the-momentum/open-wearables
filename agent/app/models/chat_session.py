from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.conversation import Conversation

from sqlalchemy import Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import CreatedAt, UpdatedAt, UUIDPrimaryKey


class ChatSession(BaseDbModel):
    __tablename__ = "chat_sessions"

    id: Mapped[UUIDPrimaryKey]
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    conversation: Mapped["Conversation"] = relationship(back_populates="session", cascade="all")  # type: ignore[name-defined]
