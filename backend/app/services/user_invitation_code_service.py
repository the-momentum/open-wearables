import io
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import segno

from app.config import settings
from app.database import DbSession
from app.models.user_invitation_code import UserInvitationCode
from app.repositories.user_invitation_code_repository import UserInvitationCodeRepository
from app.schemas.auth import SDKTokenOrigin
from app.schemas.model_crud.credentials import (
    InvitationCodeRedeemResponse,
    InvitationCodeValidateResponse,
    InvitationEmailSent,
    UserInvitationCodeCreate,
    UserInvitationCodeGenerated,
)
from app.schemas.model_crud.credentials.user_invitation_code import normalize_invitation_code
from app.services.app_registration_service import app_registration_service
from app.services.instance_service import instance_service
from app.services.refresh_token_service import refresh_token_service
from app.services.user_service import user_service
from app.utils.email_client import send_app_invitation_email
from app.utils.exceptions import InvalidInputError, NotFoundError, ServiceUnavailableError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
INVITE_LINK_VERSION = 1


def _invalid_code() -> NotFoundError:
    return NotFoundError("Invalid or expired invitation code")


def display_code(code: str) -> str:
    """The form people read and type: K7M4-Q9XP."""
    return f"{code[:4]}-{code[4:]}"


def invite_url(code: str) -> str:
    """Link that opens the Connect app with this instance's API host and the code.

    The host and code go in the fragment: browsers never send it to the server
    behind the link, so the code stays out of its logs and Referer headers.
    """
    host = urlsplit(settings.api_base_url).netloc
    return f"{settings.connect_app_link_base}#v={INVITE_LINK_VERSION}&h={host}&c={display_code(code)}"


def qr_svg(url: str) -> str:
    """A standalone SVG document: with its namespace, so it also works as an image or a file."""
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="svg", scale=8, border=2, xmldecl=False)
    return buffer.getvalue().decode()


def qr_png(url: str) -> bytes:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=8, border=2)
    return buffer.getvalue()


class UserInvitationCodeService:
    def __init__(self) -> None:
        self.crud = UserInvitationCodeRepository(UserInvitationCode)

    def _generate_code(self) -> str:
        """Generate an 8-character alphanumeric code from unambiguous charset."""
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

    def generate(
        self,
        db_session: DbSession,
        user_id: UUID,
        developer_id: UUID,
    ) -> UserInvitationCodeGenerated:
        """Generate a new invitation code for a user."""
        user_service.get(db_session, user_id, raise_404=True)
        self.crud.revoke_active_for_user(db_session, user_id)

        now = datetime.now(timezone.utc)
        code_data = UserInvitationCodeCreate(
            id=uuid4(),
            code=self._generate_code(),
            user_id=user_id,
            created_by_id=developer_id,
            expires_at=now + timedelta(days=settings.user_invitation_code_expire_days),
            created_at=now,
        )
        self.crud.create(db_session, code_data)
        url = invite_url(code_data.code)
        return UserInvitationCodeGenerated(
            **code_data.model_dump(include={"id", "code", "user_id", "expires_at", "created_at"}),
            invite_url=url,
            qr_svg=qr_svg(url),
        )

    def email(self, db_session: DbSession, user_id: UUID, to: str | None) -> InvitationEmailSent:
        """Email the user's current invitation: the same code the dashboard shows as a QR code."""
        user = user_service.get(db_session, user_id, raise_404=True)
        invitation = self.crud.get_active_for_user(db_session, user_id)
        if invitation is None:
            raise NotFoundError("No active invitation code; generate one")
        recipient = to or (user.email if user else None)
        if not recipient:
            raise InvalidInputError("The user has no email address; pass one in the request")
        url = invite_url(invitation.code)
        organisation = instance_service.get_settings(db_session).organization_name or "Your organisation"
        sent = send_app_invitation_email(
            recipient,
            organisation=organisation,
            invite_url=url,
            server=urlsplit(settings.api_base_url).netloc,
            code=display_code(invitation.code),
            expires_at=invitation.expires_at.strftime("%-d %b %Y"),
            qr_png=qr_png(url),
        )
        if not sent:
            raise ServiceUnavailableError(
                "The email could not be sent; check the email settings (SMTP_HOST or RESEND_API_KEY)"
            )
        logger.info("App invitation emailed", user_id=user_id)
        return InvitationEmailSent(sent_to=recipient, expires_at=invitation.expires_at)

    def validate(self, db_session: DbSession, code: str) -> InvitationCodeValidateResponse:
        """Check a code without using it up, so an app can show who invited the user first."""
        invitation_code = self.crud.get_valid_by_code(db_session, normalize_invitation_code(code))
        if not invitation_code:
            raise _invalid_code()
        return InvitationCodeValidateResponse(
            expires_at=invitation_code.expires_at,
            seat_request=app_registration_service.seat_request_for(db_session, invitation_code.user_id),
        )

    def redeem(self, db_session: DbSession, code: str) -> InvitationCodeRedeemResponse:
        """Redeem an invitation code and return SDK tokens."""
        invitation_code = self.crud.claim_valid_code(db_session, normalize_invitation_code(code))
        if not invitation_code:
            raise _invalid_code()

        # Storing the new refresh token commits the claim with it, so a failure before that
        # leaves the code usable
        access_token, refresh_token = refresh_token_service.issue_sdk_tokens(
            db_session,
            user_id=invitation_code.user_id,
            origin=SDKTokenOrigin.INVITE,
            issued_by_developer_id=invitation_code.created_by_id,
        )

        return InvitationCodeRedeemResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user_id=invitation_code.user_id,
        )


user_invitation_code_service = UserInvitationCodeService()
