from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update

from app.database import DbSession
from app.models.user_invitation_code import UserInvitationCode
from app.repositories.repositories import CrudRepository
from app.schemas.user_invitation_code import UserInvitationCodeCreate


class UserInvitationCodeRepository(CrudRepository[UserInvitationCode, UserInvitationCodeCreate, BaseModel]):
    def __init__(self, model: type[UserInvitationCode]) -> None:
        super().__init__(model)

    def get_valid_by_code(self, db_session: DbSession, code: str) -> UserInvitationCode | None:
        """Get an invitation code that is not yet redeemed, not revoked, and not expired."""
        now = datetime.now(timezone.utc)
        stmt = select(self.model).where(
            self.model.code == code,
            self.model.redeemed_at.is_(None),
            self.model.revoked_at.is_(None),
            self.model.expires_at > now,
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def mark_redeemed(self, db_session: DbSession, invitation_code: UserInvitationCode) -> UserInvitationCode:
        """Mark an invitation code as redeemed."""
        invitation_code.redeemed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(invitation_code)
        return invitation_code

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
