from logging import getLogger
from typing import Any
from uuid import UUID

from billiard.einfo import ExceptionInfo

from app.config import settings
from app.database import SessionLocal
from app.models import Invitation
from app.schemas.invitation import InvitationStatus
from app.utils.email_client import send_invitation_email
from celery import Task, shared_task

logger = getLogger(__name__)


class EmailSendError(Exception):
    """Raised when email sending fails and should be retried."""

    pass


class EmailTaskBase(Task):
    """Base task class that handles failure by updating invitation status to FAILED."""

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: ExceptionInfo,
    ) -> None:
        """Called when task fails after all retries are exhausted."""
        invitation_id = args[0] if args else kwargs.get("invitation_id")
        if invitation_id:
            try:
                with SessionLocal() as db:
                    invitation = db.query(Invitation).filter(Invitation.id == UUID(invitation_id)).first()
                    if invitation and invitation.status == InvitationStatus.PENDING:
                        invitation.status = InvitationStatus.FAILED
                        db.commit()
                        logger.warning(f"Marked invitation {invitation_id} as FAILED after all retries exhausted")
            except Exception as e:
                logger.error(f"Failed to update invitation {invitation_id} to FAILED status: {e}")

        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(
    bind=True,
    base=EmailTaskBase,
    autoretry_for=(ConnectionError, TimeoutError, EmailSendError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": settings.email_max_retries},
)
def send_invitation_email_task(
    self: Task,
    invitation_id: str,
    to_email: str,
    invite_url: str,
    invited_by_email: str | None = None,
) -> dict[str, str]:
    """
    Send invitation email asynchronously with retry logic.

    This task is idempotent - it checks the invitation status before sending
    to prevent duplicate emails on retry. If all retries are exhausted,
    the invitation status is set to FAILED.

    Args:
        invitation_id: UUID of the invitation (for updating status to SENT)
        to_email: Email address to send the invitation to
        invite_url: Full URL for accepting the invitation
        invited_by_email: Email of the person who sent the invitation

    Returns:
        dict with status and message
    """
    with SessionLocal() as db:
        invitation = db.query(Invitation).filter(Invitation.id == UUID(invitation_id)).first()

        if not invitation:
            raise ValueError(f"Invitation {invitation_id} not found")

        # Skip if already sent (idempotency)
        if invitation.status == InvitationStatus.SENT:
            logger.info(f"Invitation {invitation_id} already sent, skipping")
            return {
                "status": "success",
                "message": "Invitation email already sent",
                "invitation_id": invitation_id,
            }

        # Skip if already failed (allow resend via separate action)
        if invitation.status == InvitationStatus.FAILED:
            logger.info(f"Invitation {invitation_id} previously failed, skipping")
            return {
                "status": "skipped",
                "message": "Invitation email previously failed, use resend action",
                "invitation_id": invitation_id,
            }

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError(f"Invitation {invitation_id} has invalid status: {invitation.status}")

        # Send email only if status is PENDING
        attempt = self.request.retries + 1
        logger.info(
            f"Sending invitation email for {invitation_id} (attempt {attempt}/{settings.email_max_retries + 1})"
        )
        success = send_invitation_email(to_email, invite_url, invited_by_email)

        if not success:
            raise EmailSendError(f"Failed to send invitation email for invitation {invitation_id}")

        # Update status after successful send
        try:
            invitation.status = InvitationStatus.SENT
            db.commit()
            logger.info(f"Updated invitation {invitation_id} status to SENT")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update invitation {invitation_id} status: {e}")
            raise

    return {
        "status": "success",
        "message": "Invitation email sent successfully",
        "invitation_id": invitation_id,
    }
