from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import FKApplication, FKDeveloper, FKUser, Indexed, ManyToOne, PrimaryKey, str_64
from app.models import Application
from app.schemas.auth import SDKTokenOrigin, TokenType


class RefreshToken(BaseDbModel):
    """Generic refresh token for SDK and Developer tokens.

    Stores opaque refresh tokens in the database for secure token refresh.
    The token_type field indicates whether this is an SDK token or Developer token.
    """

    __tablename__ = "refresh_token"
    __table_args__ = (
        # SDK tokens from an application point at it; admin/invite tokens point at the issuing
        # developer instead (NULL once that developer is deleted). Developer tokens have no origin.
        CheckConstraint(
            "(token_type = 'sdk' AND ("
            "(origin = 'application' AND application_id IS NOT NULL AND issued_by_developer_id IS NULL)"
            " OR (origin IN ('admin', 'invite') AND application_id IS NULL)))"
            " OR (token_type = 'developer' AND origin IS NULL"
            " AND application_id IS NULL AND issued_by_developer_id IS NULL)",
            name="ck_refresh_token_origin",
        ),
    )

    id: Mapped[PrimaryKey[str_64]]  # rt-{32 hex chars}
    token_type: Mapped[TokenType]

    # For SDK tokens
    user_id: Mapped[Indexed[FKUser] | None]
    origin: Mapped[SDKTokenOrigin | None]
    application_id: Mapped[Indexed[FKApplication] | None]
    issued_by_developer_id: Mapped[FKDeveloper | None]

    # For Developer tokens
    developer_id: Mapped[Indexed[FKDeveloper] | None]

    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    application: Mapped[ManyToOne["Application"] | None] = relationship(
        "Application",
        foreign_keys="[RefreshToken.application_id]",
    )
