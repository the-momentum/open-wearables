from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select

from app.database import DbSession
from app.models.user_invitation_code import UserInvitationCode
from app.repositories.repositories import CrudRepository
from app.schemas.user_invitation_code import UserInvitationCodeCreate


class UserInvitationCodeRepository(CrudRepository[UserInvitationCode, UserInvitationCodeCreate, BaseModel]):
    def __init__(self, model: type[UserInvitationCode]) -> None:
        super().__init__(model)

    def get_valid_by_code(self, db_session: DbSession, code: str) -> UserInvitationCode | None:
        """Get an invitation code that is not yet redeemed and not expired."""
        now = datetime.now(timezone.utc)
        stmt = select(self.model).where(
            self.model.code == code,
            self.model.redeemed_at.is_(None),
            self.model.expires_at > now,
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def mark_redeemed(self, db_session: DbSession, invitation_code: UserInvitationCode) -> UserInvitationCode:
        """Mark an invitation code as redeemed."""
        invitation_code.redeemed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(invitation_code)
        return invitation_code
