from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.constants.provider_urls import from_url_slug
from app.database import DbSession
from app.integrations.celery.tasks import start_garmin_full_backfill, sync_vendor_data
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import AuthorizationURLResponse
from app.schemas.model_crud.data_priority import (
    BulkProviderSettingsUpdate,
    ProviderSettingRead,
    ProviderSettingUpdate,
)
from app.services import DeveloperDep, user_connection_service
from app.services.provider_settings_service import provider_settings_service
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.utils.auth import ConnectAuthDep
from app.utils.exceptions import AppError, UnsupportedProviderError, unknown_provider
from app.utils.redirect_allowlist import is_allowed_redirect, with_result

router = APIRouter()
factory = ProviderFactory()


def resolve_provider(slug: str) -> ProviderName:
    try:
        return ProviderName(from_url_slug(slug))
    except ValueError:
        raise unknown_provider(slug, ("path", "provider"), (p.value for p in ProviderName)) from None


def _error_redirect(return_to: str | None, provider: ProviderName, message: str) -> RedirectResponse:
    """Back to the flow's redirect_uri with the error, or to the JSON error page when it had none."""
    if return_to:
        url = with_result(return_to, provider=provider.value, status="error", message=message)
        return RedirectResponse(url=url, status_code=303)
    return RedirectResponse(url=f"/api/v1/oauth/error?{urlencode({'message': message})}", status_code=303)


def get_oauth_strategy(provider: ProviderName) -> BaseProviderStrategy:
    """Helper to get provider strategy and ensure it supports OAuth."""
    strategy = factory.get_provider(provider.value)

    if not strategy.oauth:
        raise UnsupportedProviderError(provider.value, "OAuth")
    return strategy


@router.get(
    "/{provider}/authorize",
    summary="Get Provider Authorization URL",
    response_model=AuthorizationURLResponse,
    tags=["External: Providers"],
)
def authorize_provider(
    provider: str,
    db: DbSession,
    auth: ConnectAuthDep,
    user_id: Annotated[UUID, Query(description="User ID to connect")],
    redirect_uri: Annotated[
        str | None,
        Query(description="Where to send the browser after the provider sign-in; must be on the allowlist"),
    ] = None,
):
    """
    Initiate OAuth flow for a provider.

    Returns authorization URL where user should be redirected to log in.

    Requires an API key, a developer token, or a token scoped to `user_id`: an SDK user token
    or a connect token (`X-Open-Wearables-Connect-Token`, from `POST /users/{user_id}/connect-token`).
    `redirect_uri` must match `OAUTH_REDIRECT_ALLOWLIST` (default `openwearables://oauth/callback`),
    the dashboard origin (`FRONTEND_URL`) or `CORS_ORIGINS`. After the sign-in the browser is sent
    there with `provider`, `status` (`success` or `error`) and, on error, `message` in the query,
    replacing any parameters of the same name.
    """
    if auth.auth_type in ("sdk_token", "connect_token") and auth.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token does not match user_id")

    provider_name = resolve_provider(provider)
    strategy = get_oauth_strategy(provider_name)
    setting = provider_settings_service.get_settings_map(db).get(provider_name.value)
    if setting is not None and not setting.is_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Provider '{provider_name.value}' is not enabled")
    if redirect_uri is not None and not is_allowed_redirect(redirect_uri):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "redirect_uri is not allowed; add it to OAUTH_REDIRECT_ALLOWLIST",
        )

    assert strategy.oauth
    auth_url, state = strategy.oauth.get_authorization_url(user_id, redirect_uri)
    return AuthorizationURLResponse(authorization_url=auth_url, state=state)


@router.head("/{provider}/callback", tags=["System: OAuth"])
def probe_oauth_callback(provider: str) -> None:
    """Answer the reachability probe Withings sends when the callback URL is registered."""
    get_oauth_strategy(resolve_provider(provider))


@router.get("/{provider}/callback", tags=["System: OAuth"])
def oauth_callback(
    provider: str,
    db: DbSession,
    code: Annotated[str | None, Query(description="Authorization code from provider")] = None,
    state: Annotated[str | None, Query(description="State parameter for CSRF protection")] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
):
    """
    OAuth callback endpoint.

    Provider redirects here after user authorizes. Exchanges code for tokens. When the
    flow was started with a redirect_uri, the browser goes back there on success and on
    failure, so an app's sign-in sheet never ends on a JSON page.
    """
    provider_name = resolve_provider(provider)
    strategy = get_oauth_strategy(provider_name)
    assert strategy.oauth
    started = strategy.oauth.peek_state(state) if state else None
    return_to = started.redirect_uri if started else None

    if error:
        if state:
            strategy.oauth.discard_state(state)
        return _error_redirect(return_to, provider_name, f"{error}: {error_description or 'Unknown error'}")

    if not code or not state:
        return _error_redirect(return_to, provider_name, "Missing OAuth parameters")

    try:
        oauth_state = strategy.oauth.handle_callback(db, code, state)
    except AppError as exc:
        return _error_redirect(return_to, provider_name, exc.detail)

    # Stamp last_synced_at=now so the first periodic sync uses the connection
    # timestamp as its live-sync cursor and won't attempt to pull all history.
    previous_synced_at = user_connection_service.stamp_last_synced_at(db, oauth_state.user_id, provider_name.value)

    # Grace-period flag: automatically kick off a historical sync so integrators
    # who haven't yet adopted the explicit /sync/historical call still get backfill.
    # Controlled by HISTORICAL_SYNC_ON_CONNECT (default: true).
    if settings.historical_sync_on_connect:
        caps = strategy.capabilities
        if caps.webhook_callback:
            gap_start = user_connection_service.reconnect_gap_start(
                db, oauth_state.user_id, provider_name.value, previous_synced_at
            )
            start_garmin_full_backfill.delay(str(oauth_state.user_id), gap_start.isoformat() if gap_start else None)
        elif caps.rest_pull:
            now = datetime.now(timezone.utc)
            start_date = user_connection_service.historical_start_on_connect(
                db, oauth_state.user_id, provider_name.value, previous_synced_at, days=90
            )
            sync_vendor_data.delay(
                user_id=str(oauth_state.user_id),
                start_date=start_date.isoformat(),
                end_date=now.isoformat(),
                providers=[provider_name.value],
                is_historical=True,
            )

    # If a specific redirect_uri was requested (e.g. by frontend or an app), redirect there
    if oauth_state.redirect_uri:
        url = with_result(oauth_state.redirect_uri, provider=provider_name.value, status="success")
        return RedirectResponse(url=url, status_code=303)

    # Otherwise, redirect to internal success page
    return RedirectResponse(
        url=f"/api/v1/oauth/success?provider={provider_name.value}&user_id={oauth_state.user_id}",
        status_code=303,
    )


@router.get("/success", tags=["System: OAuth"])
def oauth_success(
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


@router.get("/error", tags=["System: OAuth"])
def oauth_error(
    message: Annotated[str, Query()] = "OAuth authentication failed",
) -> dict:
    """OAuth error page."""
    return {
        "success": False,
        "message": message,
    }


@router.get("/providers", response_model=list[ProviderSettingRead], tags=["External: Providers"])
def get_providers(
    db: DbSession,
    enabled_only: Annotated[bool, Query(description="Return only enabled providers")] = False,
    cloud_only: Annotated[bool, Query(description="Return only cloud (OAuth) providers")] = False,
):
    """
    Get providers with their configuration and metadata.

    Query params:
    - enabled_only: Filter to only enabled providers (default: False, returns all)
    - cloud_only: Filter to only providers with cloud OAuth API (default: False)

    Returns full provider details including name, icon_url, has_cloud_api, is_enabled.
    """
    all_providers = provider_settings_service.get_all_providers(db)

    return [p for p in all_providers if (not enabled_only or p.is_enabled) and (not cloud_only or p.has_cloud_api)]


@router.put("/providers/{provider}", response_model=ProviderSettingRead, tags=["Internal: Providers"])
def update_provider_setting(
    provider: str,
    update: ProviderSettingUpdate,
    db: DbSession,
    _developer: DeveloperDep,
):
    """Update is_enabled and/or live_sync_mode for a single provider."""
    return provider_settings_service.update_provider_setting(db, provider, update)


@router.put("/providers", response_model=list[ProviderSettingRead], tags=["Internal: Providers"])
def bulk_update_providers(
    updates: BulkProviderSettingsUpdate,
    db: DbSession,
    _developer: DeveloperDep,
):
    """
    Bulk update provider settings.

    Accepts a map of provider_id -> is_enabled and updates all providers at once.
    This is the primary endpoint for the admin UI to save checkbox states.
    """
    return provider_settings_service.bulk_update_providers(db, updates.providers)
