from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDeveloper, FKUser, PrimaryKey, Unique, datetime_tz, str_10


class UserInvitationCode(BaseDbModel):
    """Single-use invitation code for SDK user onboarding.

    A developer generates a code for a specific user_id. The mobile app user
    enters this code, which is exchanged for SDK access_token + refresh_token.
    """

    __tablename__ = "user_invitation_code"
    __table_args__ = (Index("idx_user_invitation_code_user_id", "user_id"),)

    id: Mapped[PrimaryKey[UUID]]
    code: Mapped[Unique[str_10]]
    user_id: Mapped[FKUser]
    created_by_id: Mapped[FKDeveloper]
    expires_at: Mapped[datetime_tz]
    redeemed_at: Mapped[datetime_tz | None]
    revoked_at: Mapped[datetime_tz | None]
    created_at: Mapped[datetime_tz]
