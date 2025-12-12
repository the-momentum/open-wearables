from sqlalchemy import select

from app.database import DbSession
from app.models import Invitation
from app.repositories.repositories import CrudRepository
from app.schemas.invitation import InvitationCreate, InvitationStatus


class InvitationRepository(CrudRepository[Invitation, InvitationCreate, InvitationCreate]):
    def __init__(self, model: type[Invitation]) -> None:
        super().__init__(model)

    def get_by_token(self, db_session: DbSession, token: str) -> Invitation | None:
        """Get an invitation by its token."""
        stmt = select(self.model).where(self.model.token == token)
        return db_session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, db_session: DbSession, email: str) -> Invitation | None:
        """Get the most recent pending invitation for an email."""
        stmt = (
            select(self.model)
            .where(self.model.email == email, self.model.status == InvitationStatus.PENDING)
            .order_by(self.model.created_at.desc())
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def get_pending_invitations(self, db_session: DbSession) -> list[Invitation]:
        """Get all pending invitations."""
        stmt = (
            select(self.model)
            .where(self.model.status == InvitationStatus.PENDING)
            .order_by(self.model.created_at.desc())
        )
        return list(db_session.execute(stmt).scalars().all())

