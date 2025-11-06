from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, datetime_tz, str_64


class UserConnection(BaseDbModel):
    """OAuth connections to external cloud providers (Suunto, Garmin, Polar, Coros)"""

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        Index(
            "idx_user_connections_token_expiry",
            "token_expires_at",
            postgresql_where="status = 'active'",
        ),
        Index("idx_user_connections_user_provider", "user_id", "provider"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    provider: Mapped[str_64]  # 'suunto', 'garmin', 'polar', 'coros'

    # Provider user data
    provider_user_id: Mapped[str | None]
    provider_username: Mapped[str | None]

    # OAuth tokens
    access_token: Mapped[str]
    refresh_token: Mapped[str | None]
    token_expires_at: Mapped[datetime_tz]
    scope: Mapped[str | None]

    # Metadata
    status: Mapped[str_64]  # 'active', 'revoked', 'expired'
    last_synced_at: Mapped[datetime_tz | None]
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]
