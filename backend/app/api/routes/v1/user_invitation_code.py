from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.config import settings
from app.database import DbSession
from app.schemas.model_crud.credentials import (
    InvitationCodeRedeemResponse,
    InvitationCodeValidateResponse,
    UserInvitationCodeGenerated,
    UserInvitationCodeRedeem,
)
from app.services import DeveloperDep
from app.services.user_invitation_code_service import user_invitation_code_service
from app.utils.rate_limit import rate_limit

router = APIRouter()

# Validate and redeem share one budget: guessing works through either.
_code_attempts = Depends(rate_limit("invitation_code", limit=lambda: settings.invitation_code_rate_limit_per_minute))


@router.post(
    "/users/{user_id}/invitation-code",
    status_code=status.HTTP_201_CREATED,
)
def generate_invitation_code(
    user_id: UUID,
    db: DbSession,
    developer: DeveloperDep,
) -> UserInvitationCodeGenerated:
    """Generate a single-use invitation code for standalone SDK onboarding.

    Issues a single-use code that a mobile app can redeem (via
    `POST /api/v1/invitation-code/redeem`) to receive SDK access and refresh
    tokens - without your backend having to mint and forward a token itself.
    Any previously generated codes for this user are marked as expired.

    The response also carries `invite_url`, a link that opens the Open Wearables
    Connect app with this server and code filled in, and `qr_svg`, the same link
    as a QR code to show on screen or print.

    This is a convenience mechanism for apps with no backend of their own (for
    example the Open Wearables app or quick manual testing). It is not the
    standard integration path: if your app authenticates users against your own
    backend, mint a token directly with `POST /api/v1/users/{user_id}/token`
    instead.

    Requires developer authentication.
    """
    return user_invitation_code_service.generate(db, user_id, developer.id)


@router.post(
    "/invitation-code/validate",
    dependencies=[_code_attempts],
)
def validate_invitation_code(
    payload: UserInvitationCodeRedeem,
    db: DbSession,
) -> InvitationCodeValidateResponse:
    """Check that an invitation code can still be redeemed, without using it up.

    Public endpoint (no authentication required). Lets an app show a confirmation
    screen - who invited the user, until when the code is valid - before anything
    is exchanged. Returns 404 for an unknown, used, revoked or expired code, the
    same as redeem.

    The code is accepted as issued (`K7M4Q9XP`) or as displayed (`K7M4-Q9XP`), in
    any letter case. Validate and redeem share a limit of attempts per client IP
    (`INVITATION_CODE_RATE_LIMIT_PER_MINUTE`, default 10); over it they return 429.
    """
    return user_invitation_code_service.validate(db, payload.code)


@router.post(
    "/invitation-code/redeem",
    dependencies=[_code_attempts],
)
def redeem_invitation_code(
    payload: UserInvitationCodeRedeem,
    db: DbSession,
) -> InvitationCodeRedeemResponse:
    """Redeem a single-use invitation code for SDK tokens.

    Public endpoint (no authentication required). Exchanges a valid, non-expired,
    single-use invitation code for `access_token`, `refresh_token`, and `user_id`.
    The returned token is write-only to the `/sdk/*` endpoints. A code can be
    redeemed once, also when two requests race for it. Shares the per-IP attempt
    limit with validate.

    This backs the standalone onboarding flow used by the Open Wearables app and
    the SDK example apps. It is not the standard integration path - if your app
    has its own backend, mint and forward a token with
    `POST /api/v1/users/{user_id}/token` instead of redeeming codes on the client.
    """
    return user_invitation_code_service.redeem(db, payload.code)
