"""HTTP client for Open Wearables backend API."""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OpenWearablesClient:
    """Client for interacting with Open Wearables REST API."""

    def __init__(self) -> None:
        self.base_url = settings.open_wearables_api_url.rstrip("/")
        self.timeout = settings.request_timeout
        self._api_key = settings.open_wearables_api_key.get_secret_value()

    def _get_api_key(self) -> str:
        """Get the API key for the current request.

        In HTTP transport mode, the API key is stored in the OAuth access token's
        claims (set during the OAuth authorization flow). In stdio mode, falls back
        to the configured OPEN_WEARABLES_API_KEY from settings.
        """
        try:
            from fastmcp.server.dependencies import get_access_token

            token = get_access_token()
            if token:
                # OAuth flow stores the API key in claims
                api_key = getattr(token, "claims", {}).get("api_key")
                if api_key:
                    return api_key
        except (RuntimeError, LookupError):
            pass

        return self._api_key

    def _ensure_configured(self) -> None:
        """Raise an error if no API key is available."""
        if not self._get_api_key():
            from app.config import Settings

            env_file = Settings.model_config.get("env_file")
            raise ValueError(f"No API key available. Set OPEN_WEARABLES_API_KEY in: {env_file}")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests, using the current request's API key."""
        return {
            "X-Open-Wearables-API-Key": self._get_api_key(),
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an HTTP request to the backend API."""
        self._ensure_configured()
        url = f"{self.base_url}{path}"
        logger.debug(f"Making {method} request to {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                **kwargs,
            )

            if response.status_code == 401:
                raise ValueError("Invalid API key. Check your OPEN_WEARABLES_API_KEY configuration.")
            if response.status_code == 404:
                raise ValueError(f"Resource not found: {path}")

            response.raise_for_status()
            return response.json()

    async def get_users(self, search: str | None = None, limit: int = 100) -> dict[str, Any]:
        """
        List users accessible via the configured API key.

        Args:
            search: Optional search term to filter users by name/email
            limit: Maximum number of users to return

        Returns:
            Paginated response with users list
        """
        params = {"limit": limit}
        if search:
            params["search"] = search

        return await self._request("GET", "/api/v1/users", params=params)

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """
        Get a specific user by ID.

        Args:
            user_id: UUID of the user

        Returns:
            User details
        """
        return await self._request("GET", f"/api/v1/users/{user_id}")

    async def get_sleep_summaries(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get sleep summaries for a user within a date range.

        Args:
            user_id: UUID of the user
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            limit: Maximum number of records to return

        Returns:
            Paginated response with sleep summaries
        """
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        return await self._request("GET", f"/api/v1/users/{user_id}/summaries/sleep", params=params)

    async def get_workouts(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        record_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get workouts for a user within a date range.

        Args:
            user_id: UUID of the user
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            record_type: Optional workout type filter (e.g., "running", "cycling")
            limit: Maximum number of records to return

        Returns:
            Paginated response with workout records
        """
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        if record_type:
            params["record_type"] = record_type
        return await self._request("GET", f"/api/v1/users/{user_id}/events/workouts", params=params)

    async def get_activity_summaries(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get activity summaries for a user within a date range.

        Args:
            user_id: UUID of the user
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            limit: Maximum number of records to return

        Returns:
            Paginated response with activity summaries
        """
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        return await self._request("GET", f"/api/v1/users/{user_id}/summaries/activity", params=params)


# Singleton instance
client = OpenWearablesClient()
