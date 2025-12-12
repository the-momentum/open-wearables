import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def _get_from_address() -> str:
    """Get the formatted from address."""
    return f"{settings.email_from_name} <{settings.email_from_address}>"


def _is_email_configured() -> bool:
    """Check if email sending is properly configured."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured, skipping email send")
        return False
    if not settings.email_from_address:
        logger.warning("EMAIL_FROM_ADDRESS not configured, skipping email send")
        return False
    return True


def send_invitation_email(to_email: str, invite_url: str, invited_by_email: str | None = None) -> bool:
    """
    Send an invitation email to a new team member.

    Args:
        to_email: Email address to send the invitation to
        invite_url: Full URL for accepting the invitation
        invited_by_email: Email of the person who sent the invitation

    Returns:
        True if email was sent successfully, False otherwise
    """
    if not _is_email_configured():
        return False

    resend.api_key = settings.resend_api_key

    invited_by_text = f" by {invited_by_email}" if invited_by_email else ""

    try:
        from_addr = _get_from_address()
        logger.info(f"Sending invitation email from '{from_addr}' to '{to_email}'")

        result = resend.Emails.send({
            "from": from_addr,
            "to": [to_email],
            "subject": f"You've been invited to join {settings.email_from_name}",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>You're Invited!</h2>
                    <p>You've been invited{invited_by_text} to join the team.</p>
                    <p style="margin: 30px 0;">
                        <a href="{invite_url}"
                           style="background-color: #000; color: #fff; padding: 12px 24px;
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            Accept Invitation
                        </a>
                    </p>
                    <p style="color: #666; font-size: 14px;">
                        This invitation will expire in {settings.invitation_expire_days} days.
                    </p>
                    <p style="color: #666; font-size: 14px;">
                        If you didn't expect this invitation, you can safely ignore this email.
                    </p>
                </div>
            """,
        })
        logger.info(f"Invitation email sent to {to_email}, result: {result}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send invitation email to {to_email}: {e}")
        return False

