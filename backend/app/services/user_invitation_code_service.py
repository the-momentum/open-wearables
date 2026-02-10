import secrets
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import DbSession
from app.models.user_invitation_code import UserInvitationCode
from app.repositories.user_invitation_code_repository import UserInvitationCodeRepository
from app.schemas.user_invitation_code import (
    InvitationCodeRedeemResponse,
    UserInvitationCodeCreate,
    UserInvitationCodeRead,
)
from app.services.refresh_token_service import refresh_token_service
from app.services.sdk_token_service import create_sdk_user_token
from app.services.user_service import user_service

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


class UserInvitationCodeService:
    def __init__(self, log: Logger) -> None:
        self.crud = UserInvitationCodeRepository(UserInvitationCode)
        self.logger = log

    def _generate_code(self) -> str:
        """Generate an 8-character alphanumeric code from unambiguous charset."""
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

    def generate(
        self,
        db_session: DbSession,
        user_id: UUID,
        developer_id: UUID,
    ) -> UserInvitationCodeRead:
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
        row = self.crud.create(db_session, code_data)
        return UserInvitationCodeRead.model_validate(row)

    def redeem(self, db_session: DbSession, code: str) -> InvitationCodeRedeemResponse:
        """Redeem an invitation code and return SDK tokens."""
        invitation_code = self.crud.get_valid_by_code(db_session, code.upper())

        if not invitation_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invitation code",
            )

        self.crud.mark_redeemed(db_session, invitation_code)

        app_id = f"invite:{invitation_code.created_by_id}"

        access_token = create_sdk_user_token(
            app_id=app_id,
            user_id=str(invitation_code.user_id),
        )

        refresh_token = refresh_token_service.create_sdk_refresh_token(
            db_session,
            user_id=invitation_code.user_id,
            app_id=app_id,
        )

        return InvitationCodeRedeemResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user_id=invitation_code.user_id,
        )


user_invitation_code_service = UserInvitationCodeService(log=getLogger(__name__))
