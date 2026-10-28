from typing import Any
from uuid import UUID

from billiard.einfo import ExceptionInfo
from celery import Task, shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.models import Invitation
from app.schemas.model_crud.user_management import InvitationStatus
from app.utils.email_client import get_email_config_error, send_invitation_email
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


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
                        logger.warning(
                            f"Marked invitation {invitation_id} as FAILED after all retries exhausted",
                            provider="email",
                            task="send_invitation_email_task",
                        )
            except Exception as e:
                logger.error(
                    "Failed to update invitation to FAILED status",
                    exc_info=e,
                    provider="email",
                    task="send_invitation_email_task",
                    invitation_id=invitation_id,
                )

        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(
    name=CeleryTask.SEND_INVITATION_EMAIL,
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
    user_id: str | None = None,
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
            logger.info(
                f"Invitation {invitation_id} already sent, skipping",
                provider="email",
                task="send_invitation_email_task",
            )
            return {
                "status": "success",
                "message": "Invitation email already sent",
                "invitation_id": invitation_id,
            }

        # Skip if already failed (allow resend via separate action)
        if invitation.status == InvitationStatus.FAILED:
            logger.info(
                f"Invitation {invitation_id} previously failed, skipping",
                provider="email",
                task="send_invitation_email_task",
            )
            return {
                "status": "skipped",
                "message": "Invitation email previously failed, use resend action",
                "invitation_id": invitation_id,
            }

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError(f"Invitation {invitation_id} has invalid status: {invitation.status}")

        # Skip sending if email is not configured (allow manual invite links)
        if config_error := get_email_config_error():
            logger.warning(
                f"{config_error}, skipping send for invitation {invitation_id}",
                provider="email",
                task="send_invitation_email_task",
            )
            return {
                "status": "skipped",
                "message": "Email not configured, invitation created but not sent",
                "invitation_id": invitation_id,
            }

        # Send email only if status is PENDING
        attempt = self.request.retries + 1
        logger.info(
            f"Sending invitation email for {invitation_id} (attempt {attempt}/{settings.email_max_retries + 1})",
            provider="email",
            task="send_invitation_email_task",
        )
        success = send_invitation_email(to_email, invite_url, invited_by_email)

        if not success:
            raise EmailSendError(f"Failed to send invitation email for invitation {invitation_id}")

        # Update status after successful send
        try:
            invitation.status = InvitationStatus.SENT
            db.commit()
            logger.info(
                f"Updated invitation {invitation_id} status to SENT",
                provider="email",
                task="send_invitation_email_task",
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to update invitation status",
                exc_info=e,
                provider="email",
                task="send_invitation_email_task",
                invitation_id=invitation_id,
            )
            raise

    return {
        "status": "success",
        "message": "Invitation email sent successfully",
        "invitation_id": invitation_id,
    }
