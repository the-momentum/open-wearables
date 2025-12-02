from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.database import DbSession
from app.schemas import (
    AuthorizationURLResponse,
    AvailableProvidersResponse,
    BulkProviderSettingsUpdate,
    ProviderName,
    ProviderSettingRead,
    ProviderSettingUpdate,
)
from app.services import DeveloperDep
from app.services.provider_settings_service import ProviderSettingsService
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory

router = APIRouter()
factory = ProviderFactory()
settings_service = ProviderSettingsService()


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


@router.get("/available_providers")
async def get_available_providers(
    db: DbSession,
    only_cloud: Annotated[bool, Query(description="Return only cloud (OAuth) providers")] = False,
) -> AvailableProvidersResponse:
    """
    Get list of available providers.

    Returns the list of providers that are currently enabled by the administrator.
    By default, all implemented providers are available unless restricted via configuration.
    """
    all_providers = settings_service.get_all_providers(db)

    enabled_providers = [
        ProviderName(p.provider) for p in all_providers if p.is_enabled and (not only_cloud or p.has_cloud_api)
    ]
    return AvailableProvidersResponse(providers=enabled_providers)


@router.get("/providers")
async def get_providers_settings(
    db: DbSession,
    _developer: DeveloperDep,
) -> list[ProviderSettingRead]:
    """
    Get all providers with their configuration (Admin).
    """
    return settings_service.get_all_providers(db)


@router.put("/providers/{provider}")
async def update_provider_status(
    provider: str,
    update: ProviderSettingUpdate,
    db: DbSession,
    _developer: DeveloperDep,
) -> ProviderSettingRead:
    """
    Update single provider enabled status (Admin).
    """
    return settings_service.update_provider_status(db, provider, update)


@router.put("/providers")
async def bulk_update_providers(
    updates: BulkProviderSettingsUpdate,
    db: DbSession,
    _developer: DeveloperDep,
) -> list[ProviderSettingRead]:
    """
    Bulk update provider settings (Admin).

    Accepts a map of provider_id -> is_enabled and updates all providers at once.
    This is the primary endpoint for the admin UI to save checkbox states.
    """
    return settings_service.bulk_update_providers(db, updates.providers)
