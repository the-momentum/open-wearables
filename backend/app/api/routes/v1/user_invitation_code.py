from uuid import UUID

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas.model_crud.credentials import (
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
def generate_invitation_code(
    user_id: UUID,
    db: DbSession,
    developer: DeveloperDep,
) -> UserInvitationCodeRead:
    """Generate a single-use invitation code for standalone SDK onboarding.

    Issues a single-use code that a mobile app can redeem (via
    `POST /api/v1/invitation-code/redeem`) to receive SDK access and refresh
    tokens - without your backend having to mint and forward a token itself.
    Any previously generated codes for this user are marked as expired.

    This is a convenience mechanism for apps with no backend of their own (for
    example the Open Wearables app or quick manual testing). It is not the
    standard integration path: if your app authenticates users against your own
    backend, mint a token directly with `POST /api/v1/users/{user_id}/token`
    instead.

    Requires developer authentication.
    """
    return user_invitation_code_service.generate(db, user_id, developer.id)


@router.post(
    "/invitation-code/redeem",
)
def redeem_invitation_code(
    payload: UserInvitationCodeRedeem,
    db: DbSession,
) -> InvitationCodeRedeemResponse:
    """Redeem a single-use invitation code for SDK tokens.

    Public endpoint (no authentication required). Exchanges a valid, non-expired,
    single-use invitation code for `access_token`, `refresh_token`, and `user_id`.
    The returned token is write-only to the `/sdk/*` endpoints.

    This backs the standalone onboarding flow used by the Open Wearables app and
    the SDK example apps. It is not the standard integration path - if your app
    has its own backend, mint and forward a token with
    `POST /api/v1/users/{user_id}/token` instead of redeeming codes on the client.
    """
    return user_invitation_code_service.redeem(db, payload.code)
