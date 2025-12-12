from sqlalchemy import select

from app.database import DbSession
from app.models import Invitation
from app.repositories.repositories import CrudRepository
from app.schemas.invitation import InvitationCreate, InvitationStatus

# Statuses that represent an active/pending invitation (not yet accepted/expired/revoked)
ACTIVE_INVITATION_STATUSES = (InvitationStatus.PENDING, InvitationStatus.SENT)


class InvitationRepository(CrudRepository[Invitation, InvitationCreate, InvitationCreate]):
    def __init__(self, model: type[Invitation]) -> None:
        super().__init__(model)

    def get_by_token(self, db_session: DbSession, token: str) -> Invitation | None:
        """Get an invitation by its token."""
        stmt = select(self.model).where(self.model.token == token)
        return db_session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, db_session: DbSession, email: str) -> Invitation | None:
        """Get the most recent active invitation for an email (pending or sent)."""
        stmt = (
            select(self.model)
            .where(self.model.email == email, self.model.status.in_(ACTIVE_INVITATION_STATUSES))
            .order_by(self.model.created_at.desc())
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def get_active_invitations(self, db_session: DbSession) -> list[Invitation]:
        """Get all active invitations (pending or sent)."""
        stmt = (
            select(self.model)
            .where(self.model.status.in_(ACTIVE_INVITATION_STATUSES))
            .order_by(self.model.created_at.desc())
        )
        return db_session.execute(stmt).scalars().all()

