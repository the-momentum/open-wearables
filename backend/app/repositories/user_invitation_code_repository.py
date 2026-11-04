from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import update

from app.database import DbSession
from app.models.user_invitation_code import UserInvitationCode
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.credentials import UserInvitationCodeCreate


class UserInvitationCodeRepository(CrudRepository[UserInvitationCode, UserInvitationCodeCreate, BaseModel]):
    def __init__(self, model: type[UserInvitationCode]) -> None:
        super().__init__(model)

    def claim_valid_code(self, db_session: DbSession, code: str) -> UserInvitationCode | None:
        """Mark a valid code as redeemed and return it, or None when it is not valid.

        The check and the write are one UPDATE, so of concurrent claims only one gets the code.
        Does not commit: the claim is committed together with the refresh token issued for it
        when that is stored, and the row stays locked until then.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(
                self.model.code == code,
                self.model.redeemed_at.is_(None),
                self.model.revoked_at.is_(None),
                self.model.expires_at > now,
            )
            .values(redeemed_at=now)
            .returning(self.model)
            .execution_options(populate_existing=True)
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def revoke_active_for_user(self, db_session: DbSession, user_id: UUID) -> None:
        """Revoke all active invitation codes for a user."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.redeemed_at.is_(None),
                self.model.revoked_at.is_(None),
                self.model.expires_at > now,
            )
            .values(revoked_at=now)
        )
        db_session.execute(stmt)
        db_session.commit()
