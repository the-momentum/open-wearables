import secrets
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import DbSession
from app.integrations.celery.tasks import send_invitation_email_task
from app.models import Developer, Invitation
from app.repositories.invitation_repository import InvitationRepository
from app.schemas.invitation import InvitationCreate, InvitationStatus
from app.services.developer_service import developer_service
from app.utils.security import get_password_hash


class InvitationService:
    def __init__(self, log: Logger) -> None:
        self.crud = InvitationRepository(Invitation)
        self.logger = log

    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    def _get_invite_url(self, token: str) -> str:
        """Generate the invitation acceptance URL."""
        return f"{settings.frontend_url}/accept-invite?token={token}"

    def _send_invitation_email_async(
        self,
        invitation: Invitation,
        invited_by_email: str | None = None,
    ) -> None:
        """Queue invitation email for async delivery with retry logic."""
        invite_url = self._get_invite_url(invitation.token)
        send_invitation_email_task.delay(
            invitation_id=str(invitation.id),
            to_email=invitation.email,
            invite_url=invite_url,
            invited_by_email=invited_by_email,
        )
        self.logger.info(f"Queued invitation email for {invitation.email}")

    def create_invitation(
        self,
        db_session: DbSession,
        payload: InvitationCreate,
        invited_by: Developer,
    ) -> Invitation:
        """Create and send a new invitation."""
        # Check if email already registered as developer
        existing_developers = developer_service.crud.get_all(
            db_session,
            filters={"email": payload.email},
            offset=0,
            limit=1,
            sort_by=None,
        )
        if existing_developers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A developer with this email already exists",
            )

        # Check for existing pending invitation
        existing_invitation = self.crud.get_by_email(db_session, payload.email)
        if existing_invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A pending invitation already exists for this email",
            )

        # Create invitation
        token = self._generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days)

        invitation = Invitation(
            id=uuid4(),
            email=payload.email,
            token=token,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            invited_by_id=invited_by.id,
        )

        db_session.add(invitation)
        db_session.commit()
        db_session.refresh(invitation)

        # Queue invitation email for async delivery (Celery task will update status to SENT on success)
        self._send_invitation_email_async(invitation, invited_by.email)

        self.logger.info(f"Created invitation")
        return invitation

    def get_active_invitations(self, db_session: DbSession) -> list[Invitation]:
        """Get all active invitations (pending or sent)."""
        return self.crud.get_active_invitations(db_session)

    def accept_invitation(
        self,
        db_session: DbSession,
        token: str,
        first_name: str,
        last_name: str,
        password: str,
    ) -> Developer:
        """Accept an invitation and create a developer account.

        Creates developer and updates invitation status in a single atomic
        transaction: both operations succeed together, or both are rolled back.
        """
        invitation = self.crud.get_by_token(db_session, token)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.SENT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation is {invitation.status}",
            )

        if invitation.expires_at < datetime.now(timezone.utc):
            invitation.status = InvitationStatus.EXPIRED
            db_session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired",
            )

        try:
            # Create the developer directly (bypassing repository commit for atomicity)
            developer = Developer(
                id=uuid4(),
                email=invitation.email,
                first_name=first_name,
                last_name=last_name,
                hashed_password=get_password_hash(password),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(developer)

            # Mark invitation as accepted
            invitation.status = InvitationStatus.ACCEPTED

            # Single commit for both operations - atomic transaction
            db_session.commit()
            db_session.refresh(developer)
        except Exception as e:
            db_session.rollback()
            self.logger.error(f"Failed to accept invitation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create developer account",
            )

        self.logger.info(f"Invitation accepted")
        return developer

    def revoke_invitation(self, db_session: DbSession, invitation_id: UUID) -> Invitation:
        """Revoke an active invitation."""
        invitation = self.crud.get(db_session, invitation_id)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.SENT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot revoke invitation with status: {invitation.status}",
            )

        invitation.status = InvitationStatus.REVOKED
        db_session.commit()
        db_session.refresh(invitation)

        self.logger.info(f"Invitation revoked for {invitation.email}")
        return invitation

    def resend_invitation(self, db_session: DbSession, invitation_id: UUID) -> Invitation:
        """Resend an invitation email."""
        invitation = self.crud.get(db_session, invitation_id)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.SENT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resend invitation with status: {invitation.status}",
            )

        # Generate new token, extend expiry, and reset status to PENDING
        invitation.token = self._generate_token()
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days)
        invitation.status = InvitationStatus.PENDING
        db_session.commit()
        db_session.refresh(invitation)

        # Queue email for async delivery (will update status to SENT on success)
        invited_by_email = invitation.invited_by.email if invitation.invited_by else None
        self._send_invitation_email_async(invitation, invited_by_email)

        self.logger.info(f"Invitation resent")
        return invitation


invitation_service = InvitationService(log=getLogger(__name__))

