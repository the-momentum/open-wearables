"""Simple API client for making authenticated requests to provider APIs."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import ReauthRequiredError
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Rate limiting configuration (Garmin: 100 req / 60s window)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 15.0  # Base delay for exponential backoff (seconds): 15s, 30s, 60s

# Tokens are refreshed this long before they expire.
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

# Session.info key of the per-session token cache: (user_id, provider) -> (access_token, token_expires_at).
# A sync makes many provider requests on one session; without the cache each of them re-reads user_connection.
_TOKEN_CACHE_KEY = "provider_access_tokens"


def _token_cache(db: DbSession) -> dict[tuple[UUID, str], tuple[str, datetime | None]]:
    return db.info.setdefault(_TOKEN_CACHE_KEY, {})


def _is_fresh(token_expires_at: datetime | None) -> bool:
    return not token_expires_at or token_expires_at >= datetime.now(timezone.utc) + TOKEN_REFRESH_BUFFER


def invalidate_cached_token(db: DbSession, user_id: UUID, provider_name: str) -> None:
    """Drop the session's cached token, so the next get_valid_token reads the connection again."""
    _token_cache(db).pop((user_id, provider_name), None)


def get_valid_token(
    db: DbSession,
    user_id: UUID,
    provider_name: str,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    *,
    revoke_on_failure: bool = True,
) -> str:
    """Get a valid access token, refreshing if necessary.

    Used by make_authenticated_request and by calls that send the token outside
    of it, e.g. provider deregistration. A fresh token is cached on the session,
    so repeated calls within one sync don't query user_connection again.
    """
    cache = _token_cache(db)
    cache_key = (user_id, provider_name)
    cached = cache.get(cache_key)
    if cached and _is_fresh(cached[1]):
        return cached[0]
    cache.pop(cache_key, None)

    connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User not connected to {provider_name}",
        )

    # SDK-based providers don't have access tokens
    if not connection.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No access token available for {provider_name} (SDK-based provider?)",
        )

    # Check if token is expired (with 5 minute buffer)
    if not _is_fresh(connection.token_expires_at):
        # Scope distributed lock per user/provider to avoid concurrent refresh race conditions.

        redis_client = get_redis_client()
        lock_key = f"token_refresh_lock:{provider_name}:{user_id}"

        with redis_client.lock(lock_key, timeout=60, blocking_timeout=10, sleep=0.2):
            # Fetch and refresh connection instance inside the lock
            connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"User not connected to {provider_name}",
                )
            if not connection.access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"No access token available for {provider_name} (SDK-based provider?)",
                )

            db.refresh(connection)

            # 1. If the token never expires, return it directly
            # 2. If it expires in the future (> 5 min buffer), return existing token
            if _is_fresh(connection.token_expires_at):
                cache[cache_key] = (connection.access_token, connection.token_expires_at)
                return connection.access_token

            now = datetime.now(timezone.utc)

            # Expired with nothing to refresh it with: the grant is dead, so revoke it like a
            # rejected refresh token (stops retries, emits connection.revoked).
            if not connection.refresh_token:
                # Inside the refresh buffer but not yet expired: keep using the token until it dies.
                if connection.token_expires_at and connection.token_expires_at > now:
                    return connection.access_token
                if revoke_on_failure:
                    oauth.revoke_connection(db, user_id, reason="no_refresh_token")
                raise ReauthRequiredError(
                    provider_name,
                    user_id,
                    f"Token expired and no refresh token available for {provider_name}; reconnection required",
                )

            # Not cached: the next call reads the refreshed connection once and caches it.
            token_response = oauth.refresh_access_token(
                db, user_id, connection.refresh_token, revoke_on_failure=revoke_on_failure
            )
            return token_response.access_token

    cache[cache_key] = (connection.access_token, connection.token_expires_at)
    return connection.access_token


def _reload_token_after_401(
    db: DbSession,
    user_id: UUID,
    provider_name: str,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    rejected_token: str,
) -> str | None:
    """Re-read the token after the provider rejected it; return it only if it changed.

    The rejected token may come from the session cache while another worker has
    already refreshed the connection, which revokes the old access token at some providers.
    """
    invalidate_cached_token(db, user_id, provider_name)
    token = get_valid_token(db, user_id, provider_name, connection_repo, oauth)
    return token if token != rejected_token else None


def make_authenticated_request(
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    api_base_url: str,
    provider_name: str,
    endpoint: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    expect_json: bool = True,
    http2: bool = False,
    check_body_errors: bool = True,
) -> Any:
    """Make authenticated request to provider API.

    Handles token refresh automatically if needed.

    Args:
        db: Database session
        user_id: User ID
        connection_repo: Repository to fetch user connections
        oauth: OAuth instance for token refresh
        api_base_url: Base URL of the provider API
        provider_name: Name of the provider (for error messages)
        endpoint: API endpoint path (e.g., "/v3/workouts/")
        method: HTTP method (default: GET)
        params: Query parameters
        form_data: Form-encoded request body, mutually exclusive with json_data.
            Used by providers whose API is RPC-over-POST, e.g. Withings.
        headers: Additional headers (Authorization header will be added automatically)
        json_data: JSON body for POST/PUT requests
        expect_json: Whether to parse response as JSON (default True).
            Set to False for endpoints that return empty bodies (e.g., 202 Accepted).
        http2: Enable HTTP/2 for this request (default False). Requires the h2
            package (installed via httpx[http2]).  Use for providers that require
            HTTP/2, e.g. Sensor Bio.  Other providers are unaffected.
        check_body_errors: Raise when a 200 body carries an ``error`` or a non-200 ``code``
            (default True). Set to False for providers whose envelope carries its own
            status, e.g. Withings, so the caller can tell a throttle from a failure.

    Returns:
        Any: API response JSON, or dict with status_code if expect_json=False

    Raises:
        HTTPException: If API request fails
    """
    if form_data is not None and json_data is not None:
        raise ValueError("form_data and json_data are mutually exclusive")

    # Get valid token (will auto-refresh if needed)
    access_token = get_valid_token(db, user_id, provider_name, connection_repo, oauth)

    # Prepare headers
    request_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    # Make request with retry logic for rate limiting
    url = f"{api_base_url}{endpoint}"
    token_reloaded = False

    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(http2=http2) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params or {},
                    data=form_data,
                    json=json_data,
                    timeout=settings.provider_request_timeout_seconds,
                )

            # Handle 429 rate limiting with retry
            if response.status_code == 429:
                if attempt < MAX_RETRIES:
                    backoff_delay = RETRY_BASE_DELAY * (2**attempt)  # 1s, 2s, 4s
                    log_structured(
                        logger,
                        "warning",
                        "Rate limited (429), retrying",
                        provider_name=provider_name,
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        backoff_delay=backoff_delay,
                    )
                    time.sleep(backoff_delay)
                    continue
                # Max retries exceeded
                log_structured(
                    logger,
                    "error",
                    "Rate limited (429), max retries exceeded",
                    provider_name=provider_name,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"{provider_name.capitalize()} API error: {response.text}",
                )

            response.raise_for_status()

            # Handle non-JSON responses (e.g., 202 Accepted with empty body)
            if not expect_json:
                return {
                    "status_code": response.status_code,
                    "accepted": response.status_code == 202,
                }

            result = response.json()

            # Some APIs (like Suunto) return 200 OK but include error in response body
            if check_body_errors and isinstance(result, dict):
                # Check for common error patterns
                # Only treat as error if "error" field has a value (not None/null)
                has_error = result.get("error") is not None and result.get("error")
                has_error_code = "code" in result and result.get("code") not in (200, None)

                if has_error or has_error_code:
                    error_msg = result.get("message") or result.get("error") or str(result)
                    log_structured(
                        logger,
                        "error",
                        "API returned error in body",
                        provider_name=provider_name,
                        error_msg=error_msg,
                    )
                    raise HTTPException(
                        status_code=result.get("code", 400),
                        detail=f"{provider_name.capitalize()} API error: {error_msg}",
                    )

            return result

        except httpx.HTTPStatusError as e:
            # Handle 429 from raise_for_status (shouldn't happen due to early check, but just in case)
            if e.response.status_code == 429 and attempt < MAX_RETRIES:
                backoff_delay = RETRY_BASE_DELAY * (2**attempt)
                log_structured(
                    logger,
                    "warning",
                    "Rate limited (429), retrying",
                    provider_name=provider_name,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                    backoff_delay=backoff_delay,
                )
                time.sleep(backoff_delay)
                continue

            if e.response.status_code == 401 and not token_reloaded and attempt < MAX_RETRIES:
                token_reloaded = True
                if new_token := _reload_token_after_401(
                    db, user_id, provider_name, connection_repo, oauth, access_token
                ):
                    access_token = new_token
                    request_headers["Authorization"] = f"Bearer {access_token}"
                    continue

            log_structured(
                logger,
                "error",
                "API error",
                provider_name=provider_name,
                user_id=str(user_id),
                error=e.response.text,
            )
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=f"{provider_name.capitalize()} authorization expired. Please re-authorize.",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"{provider_name.capitalize()} API error: {e.response.text}",
            )
        except HTTPException:
            # Re-raise HTTPExceptions as-is
            raise
        except Exception as e:
            log_structured(
                logger,
                "error",
                "API request failed",
                provider_name=provider_name,
                user_id=str(user_id),
                error=str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch data from {provider_name.capitalize()}: {str(e)}",
            )

    # Should not reach here, but just in case
    raise HTTPException(
        status_code=500,
        detail=f"Failed to complete request to {provider_name.capitalize()} after retries",
    )


def download_binary_content(
    db: DbSession,
    user_id: UUID,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    provider_name: str,
    url: str,
) -> bytes:
    """Download binary content from a full URL using OAuth Bearer authentication.

    Used for endpoints that return binary data (e.g. Garmin activityFiles FIT download).
    The URL may contain additional auth params (e.g. token=...) alongside the Bearer header.
    Retries up to MAX_RETRIES times on 429 with exponential backoff.
    """
    access_token = get_valid_token(db, user_id, provider_name, connection_repo, oauth)
    headers = {"Authorization": f"Bearer {access_token}"}
    token_reloaded = False

    for attempt in range(MAX_RETRIES + 1):
        response = httpx.get(
            url, headers=headers, timeout=settings.provider_request_timeout_seconds, follow_redirects=True
        )
        if response.status_code == 401 and not token_reloaded and attempt < MAX_RETRIES:
            token_reloaded = True
            if new_token := _reload_token_after_401(db, user_id, provider_name, connection_repo, oauth, access_token):
                access_token = new_token
                headers["Authorization"] = f"Bearer {access_token}"
                continue
        if response.status_code == 429 and attempt < MAX_RETRIES:
            backoff_delay = RETRY_BASE_DELAY * (2**attempt)
            log_structured(
                logger,
                "warning",
                "Rate limited (429) on binary download, retrying",
                provider_name=provider_name,
                attempt=attempt + 1,
                max_retries=MAX_RETRIES,
                backoff_delay=backoff_delay,
            )
            time.sleep(backoff_delay)
            continue
        response.raise_for_status()
        return response.content

    raise HTTPException(status_code=500, detail=f"Failed to download binary content from {provider_name}")
