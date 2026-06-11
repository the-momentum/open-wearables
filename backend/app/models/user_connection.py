from uuid import UUID
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName


class UserConnection(BaseDbModel):
    """OAuth connections to external cloud providers."""

    __table_args__ = (
        Index(
            "ix_user_connection_token_expiry",
            "token_expires_at",
            postgresql_where="status = 'active'",
        ),
        Index("ix_user_connection_user_provider", "user_id", "provider", unique=True),
        Index("ix_user_connection_status_user_id", "status", "user_id"),
    )
    __tablename__ = "user_connection"

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    # Explicit String(64): the column predates the ProviderName entry in
    # type_annotation_map, which maps to String(50).
    provider: Mapped[ProviderName] = mapped_column(String(64))

    # Provider user data
    provider_user_id: Mapped[str | None]
    provider_username: Mapped[str | None]

    # OAuth tokens (optional for SDK-based providers like Apple)
    access_token: Mapped[str | None]
    refresh_token: Mapped[str | None]
    token_expires_at: Mapped[datetime | None]
    scope: Mapped[str | None]

    # Metadata
    status: Mapped[ConnectionStatus]
    last_synced_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]
