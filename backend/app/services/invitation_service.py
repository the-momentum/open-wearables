import secrets
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import DbSession
from app.integrations.celery.tasks import send_invitation_email_task
from app.models import Developer, Invitation
from app.repositories.invitation_repository import InvitationRepository
from app.schemas.invitation import (
    InvitationCreate,
    InvitationCreateInternal,
    InvitationResend,
    InvitationStatus,
)
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
        self.logger.info(f"Queued invitation email for {invitation.id}")

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

        # Create invitation via repository
        invitation_data = InvitationCreateInternal(
            id=uuid4(),
            email=payload.email,
            token=self._generate_token(),
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days),
            created_at=datetime.now(timezone.utc),
            invited_by_id=invited_by.id,
        )
        invitation = self.crud.create(db_session, invitation_data)

        # Queue invitation email for async delivery (Celery task will update status to SENT on success)
        self._send_invitation_email_async(invitation, invited_by.email)

        self.logger.info("Created invitation")
        return invitation

    def get_active_invitations(self, db_session: DbSession) -> Sequence[Invitation]:
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
            self.crud.update_status(db_session, invitation, InvitationStatus.EXPIRED)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired",
            )

        # Build developer model for atomic creation
        developer = Developer(
            id=uuid4(),
            email=invitation.email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=get_password_hash(password),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        try:
            developer = self.crud.accept_with_developer(db_session, invitation, developer)
        except Exception as e:
            self.logger.error(f"Failed to accept invitation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create developer account",
            )

        self.logger.info("Invitation accepted")
        return developer

    def revoke_invitation(self, db_session: DbSession, invitation_id: UUID) -> Invitation:
        """Revoke an active invitation."""
        invitation = self.crud.get(db_session, invitation_id)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.SENT, InvitationStatus.FAILED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot revoke invitation with status: {invitation.status}",
            )

        invitation = self.crud.update_status(db_session, invitation, InvitationStatus.REVOKED)

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

        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.SENT, InvitationStatus.FAILED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resend invitation with status: {invitation.status}",
            )

        # Generate new token, extend expiry, and reset status to PENDING
        resend_data = InvitationResend(
            token=self._generate_token(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days),
            status=InvitationStatus.PENDING,
        )
        invitation = self.crud.update(db_session, invitation, resend_data)

        # Queue email for async delivery (will update status to SENT on success)
        invited_by_email = invitation.invited_by.email if invitation.invited_by else None
        self._send_invitation_email_async(invitation, invited_by_email)

        self.logger.info("Invitation resent")
        return invitation


invitation_service = InvitationService(log=getLogger(__name__))
