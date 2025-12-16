from collections.abc import Sequence

from sqlalchemy import select

from app.database import DbSession
from app.models import Developer, Invitation
from app.repositories.repositories import CrudRepository
from app.schemas.invitation import (
    InvitationCreateInternal,
    InvitationResend,
    InvitationStatus,
)

# Statuses that block creating a new invitation for the same email
# (FAILED is not included - users can create new invitations if old one failed)
BLOCKING_INVITATION_STATUSES = (InvitationStatus.PENDING, InvitationStatus.SENT)

# Statuses shown in the invitation list (includes FAILED so users can resend)
VISIBLE_INVITATION_STATUSES = (InvitationStatus.PENDING, InvitationStatus.SENT, InvitationStatus.FAILED)


class InvitationRepository(CrudRepository[Invitation, InvitationCreateInternal, InvitationResend]):
    def __init__(self, model: type[Invitation]) -> None:
        super().__init__(model)

    def get_by_token(self, db_session: DbSession, token: str) -> Invitation | None:
        """Get an invitation by its token."""
        stmt = select(self.model).where(self.model.token == token)
        return db_session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, db_session: DbSession, email: str) -> Invitation | None:
        """Get the most recent blocking invitation for an email (pending or sent).

        FAILED invitations don't block - users can create new invitations for that email.
        """
        stmt = (
            select(self.model)
            .where(self.model.email == email, self.model.status.in_(BLOCKING_INVITATION_STATUSES))
            .order_by(self.model.created_at.desc())
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def get_active_invitations(self, db_session: DbSession) -> Sequence[Invitation]:
        """Get all active invitations (pending, sent, or failed)."""
        stmt = (
            select(self.model)
            .where(self.model.status.in_(VISIBLE_INVITATION_STATUSES))
            .order_by(self.model.created_at.desc())
        )
        return db_session.execute(stmt).scalars().all()

    def update_status(
        self,
        db_session: DbSession,
        invitation: Invitation,
        status: InvitationStatus,
    ) -> Invitation:
        """Update invitation status."""
        invitation.status = status
        db_session.commit()
        db_session.refresh(invitation)
        return invitation

    def accept_with_developer(
        self,
        db_session: DbSession,
        invitation: Invitation,
        developer: Developer,
    ) -> Developer:
        """Accept invitation and create developer in a single atomic transaction."""
        db_session.add(developer)
        invitation.status = InvitationStatus.ACCEPTED
        db_session.commit()
        db_session.refresh(developer)
        return developer
