import logging
from html import escape
from typing import Any, cast

import resend
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)
_email_validator = TypeAdapter(EmailStr)


def is_valid_email(email: str) -> bool:
    """Check if the email is valid using Pydantic's EmailStr validation."""
    try:
        _email_validator.validate_python(email)
        return True
    except ValidationError:
        return False


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
    if not settings.email_from_name:
        logger.warning("EMAIL_FROM_NAME not configured, skipping email send")
        return False
    return True


def _configure_resend() -> None:
    """Configure Resend API key.

    Note: The Resend library uses module-level configuration.
    Since we use a single API key for the entire application,
    this is safe even in concurrent environments.
    """
    resend.api_key = settings.resend_api_key.get_secret_value()


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
    if not is_valid_email(to_email):
        logger.warning("Invalid email address provided")
        return False
    if not _is_email_configured():
        return False

    _configure_resend()
    invited_by_text = f" by {escape(invited_by_email)}" if invited_by_email else ""

    try:
        from_addr = _get_from_address()
        logger.info(f"Sending invitation email from '{from_addr}'")

        params = cast(
            Any,
            {
                "from": from_addr,
                "to": [to_email],
                "subject": f"You've been invited to join {escape(settings.email_from_name)}",
                "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>You're Invited!</h2>
                    <p>You've been invited{invited_by_text} to join the team.</p>
                    <p style="margin: 30px 0;">
                        <a href="{escape(invite_url)}"
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
            },
        )
        result = resend.Emails.send(params)
        logger.info(f"Invitation email sent successfully, result: {result}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send invitation email: {e}")
        return False
