from uuid import UUID

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas.user_invitation_code import (
    InvitationCodeRedeemResponse,
    UserInvitationCodeRead,
    UserInvitationCodeRedeem,
)
from app.services import DeveloperDep
from app.services.user_invitation_code_service import user_invitation_code_service

router = APIRouter()


@router.post(
    "/users/{user_id}/invitation-code",
    status_code=status.HTTP_201_CREATED,
)
async def generate_invitation_code(
    user_id: UUID,
    db: DbSession,
    developer: DeveloperDep,
) -> UserInvitationCodeRead:
    """Generate a single-use invitation code for SDK user onboarding.

    The code can be shared with a mobile app user who enters it to receive
    SDK access and refresh tokens without manually entering user_id and tokens.

    Previously generated codes for this user are marked as expired.

    Requires developer authentication.
    """
    return user_invitation_code_service.generate(db, user_id, developer.id)


@router.post(
    "/invitation-code/redeem",
)
async def redeem_invitation_code(
    payload: UserInvitationCodeRedeem,
    db: DbSession,
) -> InvitationCodeRedeemResponse:
    """Redeem an invitation code for SDK tokens.

    Public endpoint (no authentication required). Exchanges a valid,
    non-expired, single-use invitation code for access_token, refresh_token,
    and user_id.
    """
    return user_invitation_code_service.redeem(db, payload.code)
