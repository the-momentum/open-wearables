from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status

from app.database import DbSession
from app.schemas.oauth import Token
from app.schemas.sdk import SDKTokenRequest
from app.services import application_service, create_sdk_user_token
from app.utils.auth import DeveloperOptionalDep

router = APIRouter()


@router.post("/users/{user_id}/token")
async def create_user_token(
    user_id: UUID,
    db: DbSession,
    payload: Annotated[SDKTokenRequest | None, Body()] = None,
    developer: DeveloperOptionalDep = None,
) -> Token:
    """Exchange app credentials or admin auth for user-scoped access token.

    Supports two authentication methods:
    1. App credentials: Provide app_id and app_secret in the request body
    2. Admin authentication: Authenticate as a developer/admin via Bearer token
       (app_id and app_secret can be omitted)

    Returns a JWT token scoped to SDK endpoints only.
    - App-generated tokens: valid for 60 minutes
    - Admin-generated tokens: infinite (no expiration)

    Args:
        user_id: OpenWearables User ID (UUID)
        payload: Optional application credentials (app_id, app_secret)
        db: Database session
        developer: Optional authenticated developer (from Bearer token)

    Returns:
        Token containing access_token and token_type

    Raises:
        401: If app credentials are invalid or admin auth is missing
        400: If neither app credentials nor admin auth is provided
    """
    app_id: str

    # Method 1: App credentials provided
    if payload and payload.app_id and payload.app_secret:
        application = application_service.validate_credentials(db, payload.app_id, payload.app_secret)
        app_id = application.app_id
    # Method 2: Admin authentication (developer token)
    elif developer:
        # Use developer ID as app_id for admin-generated tokens (enables audit trail)
        # Format: "admin:{developer_id}" to distinguish from app-generated tokens
        app_id = f"admin:{developer.id}"
    else:
        # Neither method provided
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either app credentials (app_id, app_secret) or admin authentication (Bearer token) is required",
        )

    # Generate user-scoped SDK token
    access_token = create_sdk_user_token(
        app_id=app_id,
        user_id=str(user_id),
        infinite=True,
    )

    return Token(access_token=access_token, token_type="bearer")
