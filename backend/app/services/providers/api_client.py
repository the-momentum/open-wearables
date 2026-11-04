"""Simple API client for making authenticated requests to provider APIs."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import (
    ProviderError,
    ProviderNotConnectedError,
    ProviderTokenUnavailableError,
    ReauthRequiredError,
    provider_error_from_response,
    provider_label,
)
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Rate limiting configuration (Garmin: 100 req / 60s window)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 15.0  # Base delay for exponential backoff (seconds): 15s, 30s, 60s

# Tokens are refreshed this long before they expire.
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

# A sync makes many provider requests on one session, so the token is kept on the session instead of
# re-reading user_connection each time; only this long, so a disconnect made elsewhere stops the sync.
TOKEN_CACHE_TTL_SECONDS = 60.0

# Session.info key of that cache: (user_id, provider) -> (access_token, token_expires_at, cached at).
_TOKEN_CACHE_KEY = "provider_access_tokens"

# A grant that answers only 401/403 for this long is dead: a revoke at a provider without refresh tokens
# (Polar) or a lapsed Oura membership. A single success resets it, so a refused endpoint alone never counts.
DEAD_GRANT_AFTER = timedelta(days=1)

# Session.info key of the grants this session has already seen succeed.
_AUTH_OK_KEY = "provider_auth_ok"


def _token_cache(db: DbSession) -> dict[tuple[UUID, str], tuple[str, datetime | None, float]]:
    return db.info.setdefault(_TOKEN_CACHE_KEY, {})


def _cached_token(db: DbSession, key: tuple[UUID, str]) -> str | None:
    cache = _token_cache(db)
    if (entry := cache.get(key)) is None:
        return None
    token, expires_at, cached_at = entry
    if time.monotonic() - cached_at < TOKEN_CACHE_TTL_SECONDS and _is_token_fresh(expires_at):
        return token
    del cache[key]
    return None


def _cache_token(db: DbSession, key: tuple[UUID, str], token: str, expires_at: datetime | None) -> str:
    _token_cache(db)[key] = (token, expires_at, time.monotonic())
    return token


def _is_token_fresh(token_expires_at: datetime | None) -> bool:
    return not token_expires_at or token_expires_at >= datetime.now(timezone.utc) + TOKEN_REFRESH_BUFFER


def invalidate_cached_token(db: DbSession, user_id: UUID, provider_name: str) -> None:
    """Drop the session's cached token, so the next get_valid_token reads the connection again."""
    _token_cache(db).pop((user_id, provider_name), None)


def _body_status(result: dict[str, Any]) -> int:
    """The status a 200 body reports its error with, also when the code is a string; without
    an error status there, the provider still rejected the request, so a 400."""
    try:
        code = int(result["code"])
    except (KeyError, TypeError, ValueError):
        return 400
    return code if 400 <= code < 600 else 400


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
    of it, e.g. provider deregistration.
    """
    cache_key = (user_id, provider_name)
    if cached := _cached_token(db, cache_key):
        return cached

    connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
    if not connection:
        raise ProviderNotConnectedError(provider_name)
    connection_repo.reload_tokens(db, connection)

    # SDK-based providers don't have access tokens
    if not connection.access_token:
        raise ProviderTokenUnavailableError(provider_name)

    if not _is_token_fresh(connection.token_expires_at):
        with _refresh_lock(provider_name, user_id):
            # Fetch and refresh connection instance inside the lock
            connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
            if not connection:
                raise ProviderNotConnectedError(provider_name)
            if not connection.access_token:
                raise ProviderTokenUnavailableError(provider_name)

            connection_repo.reload_tokens(db, connection)

            # 1. If the token never expires, return it directly
            # 2. If it expires in the future (> 5 min buffer), return existing token
            if _is_token_fresh(connection.token_expires_at):
                return _cache_token(db, cache_key, connection.access_token, connection.token_expires_at)

            now = datetime.now(timezone.utc)

            # Expired with nothing to refresh it with: the grant is dead, so revoke it like a
            # rejected refresh token (stops retries, emits connection.revoked).
            if not connection.refresh_token:
                # Inside the refresh buffer but not yet expired: keep using the token until it dies.
                if connection.token_expires_at and connection.token_expires_at > now:
                    return connection.access_token
                if revoke_on_failure:
                    oauth.revoke_connection(db, user_id, reason="no_refresh_token")
                raise ReauthRequiredError(provider_name, user_id, "Token expired and no refresh token available")

            token_response = oauth.refresh_access_token(
                db, user_id, connection.refresh_token, revoke_on_failure=revoke_on_failure
            )
            # The refresh stored the new expiry on this session's connection
            return _cache_token(db, cache_key, token_response.access_token, connection.token_expires_at)

    return _cache_token(db, cache_key, connection.access_token, connection.token_expires_at)


def _failing_since_key(provider_name: str, user_id: UUID) -> str:
    return f"provider_auth_failing_since:{provider_name}:{user_id}"


def _note_auth_success(db: DbSession, user_id: UUID, provider_name: str) -> None:
    seen = db.info.setdefault(_AUTH_OK_KEY, set())
    if (user_id, provider_name) not in seen:
        get_redis_client().delete(_failing_since_key(provider_name, user_id))
        seen.add((user_id, provider_name))


def _note_auth_failure(
    db: DbSession, user_id: UUID, provider_name: str, oauth: BaseOAuthTemplate, *, revoke_on_failure: bool = True
) -> None:
    """Raise ReauthRequiredError once the grant has failed for DEAD_GRANT_AFTER, revoking it unless the caller does."""
    db.info.setdefault(_AUTH_OK_KEY, set()).discard((user_id, provider_name))
    redis_client = get_redis_client()
    key = _failing_since_key(provider_name, user_id)
    now = time.time()
    redis_client.set(key, now, nx=True, ex=int(2 * DEAD_GRANT_AFTER.total_seconds()))
    if now - float(redis_client.get(key) or now) < DEAD_GRANT_AFTER.total_seconds():
        return
    redis_client.delete(key)
    if revoke_on_failure:
        oauth.revoke_connection(db, user_id, reason="auth_failing")
    raise ReauthRequiredError(
        provider_name, user_id, f"{provider_name} rejected every request for a day; reconnection required"
    )


def _refresh_lock(provider_name: str, user_id: UUID) -> Any:
    """Per user and provider, so concurrent refreshes can't race each other."""
    return get_redis_client().lock(
        f"token_refresh_lock:{provider_name}:{user_id}", timeout=60, blocking_timeout=10, sleep=0.2
    )


def _reload_token_after_401(
    db: DbSession,
    user_id: UUID,
    provider_name: str,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
    rejected_token: str,
    *,
    revoke_on_failure: bool = True,
) -> str | None:
    """A token to retry with after the provider rejected one, or None when there is none.

    Another worker may have refreshed the connection since, which voids the old token at some
    providers. Otherwise the token is refreshed early: a grant the user revoked at the provider
    rejects its refresh token as well, which raises ReauthRequiredError and, unless
    ``revoke_on_failure`` is False, revokes the connection.
    """
    invalidate_cached_token(db, user_id, provider_name)
    cache_key = (user_id, provider_name)
    with _refresh_lock(provider_name, user_id):
        connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
        if not connection or not connection.access_token:
            return None
        connection_repo.reload_tokens(db, connection)
        if connection.access_token != rejected_token:
            return _cache_token(db, cache_key, connection.access_token, connection.token_expires_at)
        # Without a refresh token the grant can't be told apart from an endpoint the user didn't consent to
        if not connection.refresh_token:
            return None
        token_response = oauth.refresh_access_token(
            db, user_id, connection.refresh_token, revoke_on_failure=revoke_on_failure
        )
        return _cache_token(db, cache_key, token_response.access_token, connection.token_expires_at)


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
    revoke_on_failure: bool = True,
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
        revoke_on_failure: Revoke the connection when the grant turns out to be dead (default
            True). Set to False when the caller revokes it itself with a more specific reason;
            ReauthRequiredError is raised either way.

    Returns:
        Any: API response JSON, or dict with status_code if expect_json=False

    Raises:
        ProviderConnectionError: If the user's connection can't be used (see ``get_valid_token``)
            or the provider rejects the token
        ProviderError: If the request fails or the provider answers with an error
    """
    if form_data is not None and json_data is not None:
        raise ValueError("form_data and json_data are mutually exclusive")

    # Get valid token (will auto-refresh if needed)
    access_token = get_valid_token(
        db, user_id, provider_name, connection_repo, oauth, revoke_on_failure=revoke_on_failure
    )

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
                    logger.warning(
                        "Rate limited (429), retrying",
                        provider_name=provider_name,
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        backoff_delay=backoff_delay,
                    )
                    time.sleep(backoff_delay)
                    continue
                # Max retries exceeded
                logger.error(
                    "Rate limited (429), max retries exceeded",
                    provider_name=provider_name,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                )
                raise provider_error_from_response(provider_name, response.status_code, response.text)

            response.raise_for_status()
            _note_auth_success(db, user_id, provider_name)

            # Handle non-JSON responses (e.g., 202 Accepted with empty body)
            if not expect_json:
                return {
                    "status_code": response.status_code,
                    "accepted": response.status_code == 202,
                }

            try:
                result = response.json()
            except ValueError as e:
                # e.g. an empty 204 body where the endpoint normally returns JSON
                raise ProviderError(
                    provider_name,
                    f"{provider_label(provider_name)} API returned an invalid response",
                    upstream_status=response.status_code,
                    upstream_body=response.text,
                ) from e

            # Some APIs (like Suunto) return 200 OK but include error in response body
            if check_body_errors and isinstance(result, dict):
                # Check for common error patterns
                # Only treat as error if "error" field has a value (not None/null)
                has_error = result.get("error") is not None and result.get("error")
                has_error_code = "code" in result and result.get("code") not in (200, None)

                if has_error or has_error_code:
                    error_msg = result.get("message") or result.get("error") or str(result)
                    logger.error(
                        "API returned error in body",
                        provider_name=provider_name,
                        error_msg=error_msg,
                    )
                    raise provider_error_from_response(provider_name, _body_status(result), response.text)

            return result

        except httpx.HTTPStatusError as e:
            # Handle 429 from raise_for_status (shouldn't happen due to early check, but just in case)
            if e.response.status_code == 429 and attempt < MAX_RETRIES:
                backoff_delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
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
                    db,
                    user_id,
                    provider_name,
                    connection_repo,
                    oauth,
                    access_token,
                    revoke_on_failure=revoke_on_failure,
                ):
                    access_token = new_token
                    request_headers["Authorization"] = f"Bearer {access_token}"
                    continue
            if e.response.status_code in (401, 403):
                _note_auth_failure(db, user_id, provider_name, oauth, revoke_on_failure=revoke_on_failure)

            logger.error(
                "API error",
                provider_name=provider_name,
                user_id=str(user_id),
                error=e.response.text,
            )
            raise provider_error_from_response(provider_name, e.response.status_code, e.response.text) from e
        except httpx.RequestError as e:
            logger.error(
                "API request failed",
                provider_name=provider_name,
                user_id=str(user_id),
                error=str(e),
            )
            raise ProviderError(provider_name) from e

    # Should not reach here, but just in case
    raise ProviderError(provider_name, f"Failed to complete request to {provider_label(provider_name)} after retries")


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
        try:
            response = httpx.get(
                url, headers=headers, timeout=settings.provider_request_timeout_seconds, follow_redirects=True
            )
        except httpx.RequestError as e:
            raise ProviderError(provider_name) from e
        if response.status_code == 401 and not token_reloaded and attempt < MAX_RETRIES:
            token_reloaded = True
            if new_token := _reload_token_after_401(db, user_id, provider_name, connection_repo, oauth, access_token):
                access_token = new_token
                headers["Authorization"] = f"Bearer {access_token}"
                continue
        if response.status_code == 429 and attempt < MAX_RETRIES:
            backoff_delay = RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "Rate limited (429) on binary download, retrying",
                provider_name=provider_name,
                attempt=attempt + 1,
                max_retries=MAX_RETRIES,
                backoff_delay=backoff_delay,
            )
            time.sleep(backoff_delay)
            continue
        if response.status_code in (401, 403):
            _note_auth_failure(db, user_id, provider_name, oauth)
        if response.is_error:
            raise provider_error_from_response(provider_name, response.status_code, response.text)
        _note_auth_success(db, user_id, provider_name)
        return response.content

    raise ProviderError(provider_name, f"Failed to download binary content from {provider_label(provider_name)}")
