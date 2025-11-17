from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.database import DbSession
from app.schemas.oauth import AuthorizationURLResponse
from app.services.oauth_service import oauth_service

router = APIRouter()


@router.get("/{provider}/authorize")
async def authorize_provider(
    provider: str,
    user_id: Annotated[UUID, Query(description="User ID to connect")],
    redirect_uri: Annotated[str | None, Query(description="Optional redirect URI after authorization")] = None,
) -> AuthorizationURLResponse:
    """
    Initiate OAuth flow for a provider.

    Returns authorization URL where user should be redirected to log in.
    """
    return oauth_service.generate_authorization_url(user_id, provider, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: Annotated[str, Query(description="Authorization code from provider")],
    state: Annotated[str, Query(description="State parameter for CSRF protection")],
    db: DbSession,
) -> RedirectResponse:
    """
    OAuth callback endpoint.

    Provider redirects here after user authorizes. Exchanges code for tokens.
    """
    result = oauth_service.exchange_code_for_tokens(db, provider, code, state)

    # Redirect to success page or developer's redirect_uri
    if result.get("redirect_uri"):
        redirect_url = result["redirect_uri"]
    else:
        # Default success page
        redirect_url = f"/oauth/success?provider={provider}&user_id={result['user_id']}"

    return RedirectResponse(url=redirect_url)


@router.get("/success")
async def oauth_success(
    provider: Annotated[str, Query()],
    user_id: Annotated[str, Query()],
) -> dict:
    """Simple success page after OAuth completion."""
    return {
        "success": True,
        "message": f"Successfully connected to {provider}",
        "user_id": user_id,
        "provider": provider,
    }
