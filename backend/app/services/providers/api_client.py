"""Simple API client for making authenticated requests to provider APIs."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate

logger = logging.getLogger(__name__)


def _get_valid_token(
    db: DbSession,
    user_id: UUID,
    provider_name: str,
    connection_repo: UserConnectionRepository,
    oauth: BaseOAuthTemplate,
) -> str:
    """Get a valid access token, refreshing if necessary.

    Private function used internally by make_authenticated_request.
    """
    connection = connection_repo.get_by_user_and_provider(db, user_id, provider_name)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User not connected to {provider_name}",
        )

    # Check if token is expired (with 5 minute buffer)
    if connection.token_expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
        if not connection.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token expired and no refresh token available for {provider_name}",
            )
        token_response = oauth.refresh_access_token(db, user_id, connection.refresh_token)
        return token_response.access_token

    return connection.access_token


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
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    expect_json: bool = True,
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
        headers: Additional headers (Authorization header will be added automatically)
        json_data: JSON body for POST/PUT requests
        expect_json: Whether to parse response as JSON (default True).
            Set to False for endpoints that return empty bodies (e.g., 202 Accepted).

    Returns:
        Any: API response JSON, or dict with status_code if expect_json=False

    Raises:
        HTTPException: If API request fails
    """
    # Get valid token (will auto-refresh if needed)
    access_token = _get_valid_token(db, user_id, provider_name, connection_repo, oauth)

    # Prepare headers
    request_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    # Make request
    url = f"{api_base_url}{endpoint}"

    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=request_headers,
            params=params or {},
            json=json_data,
            timeout=30.0,
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
        if isinstance(result, dict):
            # Check for common error patterns
            # Only treat as error if "error" field has a value (not None/null)
            has_error = result.get("error") is not None and result.get("error")
            has_error_code = "code" in result and result.get("code") not in (200, None)

            if has_error or has_error_code:
                error_msg = result.get("message") or result.get("error") or str(result)
                logger.error(f"{provider_name.capitalize()} API returned error in body: {error_msg}")
                raise HTTPException(
                    status_code=result.get("code", 400),
                    detail=f"{provider_name.capitalize()} API error: {error_msg}",
                )

        return result

    except httpx.HTTPStatusError as e:
        logger.error(
            f"{provider_name.capitalize()} API error for user {user_id}: {e.response.status_code} - {e.response.text}",
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
    except Exception as e:
        logger.error(f"{provider_name.capitalize()} API request failed for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch data from {provider_name.capitalize()}: {str(e)}",
        )
