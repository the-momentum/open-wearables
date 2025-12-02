from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.database import DbSession
from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.schemas import AuthorizationURLResponse, ProviderName
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory

router = APIRouter()
factory = ProviderFactory()


def get_oauth_strategy(provider: ProviderName) -> BaseProviderStrategy:
    """Helper to get provider strategy and ensure it supports OAuth."""
    strategy = factory.get_provider(provider.value)

    if not strategy.oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider.value}' does not support OAuth",
        )
    return strategy


@router.get("/{provider}/authorize")
async def authorize_provider(
    provider: ProviderName,
    user_id: Annotated[UUID, Query(description="User ID to connect")],
    redirect_uri: Annotated[str | None, Query(description="Optional redirect URI after authorization")] = None,
) -> AuthorizationURLResponse:
    """
    Initiate OAuth flow for a provider.

    Returns authorization URL where user should be redirected to log in.
    """
    strategy = get_oauth_strategy(provider)

    assert strategy.oauth
    auth_url, state = strategy.oauth.get_authorization_url(user_id, redirect_uri)
    return AuthorizationURLResponse(authorization_url=auth_url, state=state)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: ProviderName,
    code: Annotated[str, Query(description="Authorization code from provider")],
    state: Annotated[str, Query(description="State parameter for CSRF protection")],
    db: DbSession,
) -> RedirectResponse:
    """
    OAuth callback endpoint.

    Provider redirects here after user authorizes. Exchanges code for tokens.
    """
    strategy = get_oauth_strategy(provider)

    assert strategy.oauth
    oauth_state = strategy.oauth.handle_callback(db, code, state)

    # Redirect to success page or developer's redirect_uri
    redirect_url = oauth_state.redirect_uri or f"/oauth/success?provider={provider.value}&user_id={oauth_state.user_id}"

    # schedule sync task
    sync_vendor_data.delay(str(oauth_state.user_id), start_date=None, end_date=None)

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
