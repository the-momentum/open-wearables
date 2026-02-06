from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDeveloper, FKUser, Indexed, PrimaryKey, datetime_tz, str_64
from app.schemas.token_type import TokenType


class RefreshToken(BaseDbModel):
    """Generic refresh token for SDK and Developer tokens.

    Stores opaque refresh tokens in the database for secure token refresh.
    The token_type field indicates whether this is an SDK token or Developer token.
    """

    __tablename__ = "refresh_token"

    id: Mapped[PrimaryKey[str_64]]  # rt-{32 hex chars}
    token_type: Mapped[TokenType]

    # For SDK tokens
    user_id: Mapped[Indexed[FKUser] | None]
    app_id: Mapped[str_64 | None]

    # For Developer tokens
    developer_id: Mapped[Indexed[FKDeveloper] | None]

    created_at: Mapped[datetime_tz]
    last_used_at: Mapped[datetime_tz | None]
    revoked_at: Mapped[datetime_tz | None]
