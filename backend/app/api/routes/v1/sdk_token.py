from uuid import UUID

from fastapi import APIRouter

from app.database import DbSession
from app.schemas.oauth import Token
from app.schemas.sdk import SDKTokenRequest
from app.services import application_service, create_sdk_user_token

router = APIRouter()


@router.post("/users/{user_id}/token")
async def create_user_token(
    user_id: UUID,
    payload: SDKTokenRequest,
    db: DbSession,
) -> Token:
    """Exchange app credentials for user-scoped access token.

    The Developer's Backend calls this endpoint when a user logs in.
    The app's backend provides app_id and app_secret.

    Returns a JWT token valid for 60 minutes, scoped to SDK endpoints only.

    Args:
        user_id: OpenWearables User ID (UUID)
        payload: Application credentials (app_id, app_secret)
        db: Database session

    Returns:
        Token containing access_token and token_type

    Raises:
        401: If app credentials are invalid
    """
    # Validate app credentials
    application = application_service.validate_credentials(db, payload.app_id, payload.app_secret)

    # Generate user-scoped SDK token
    access_token = create_sdk_user_token(
        app_id=application.app_id,
        user_id=str(user_id),
    )

    return Token(access_token=access_token, token_type="bearer")
