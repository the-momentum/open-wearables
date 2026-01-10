"""HTTP client for the Open Wearables API."""

from __future__ import annotations

from typing import Any

import httpx

from open_wearables.exceptions import (
    AuthenticationError,
    NotFoundError,
    OpenWearablesError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class HttpClient:
    """Low-level HTTP client for making requests to the Open Wearables API."""

    DEFAULT_BASE_URL = "https://api.openwearables.io"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Get default headers for requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_client(self) -> httpx.Client:
        """Get or create the synchronous HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._client

    def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create the asynchronous HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._async_client

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError(
                "Invalid or missing API key",
                status_code=response.status_code,
                response=response.text,
            )
        elif response.status_code == 404:
            raise NotFoundError(
                "Resource not found",
                status_code=response.status_code,
                response=response.text,
            )
        elif response.status_code == 422:
            raise ValidationError(
                "Validation error",
                status_code=response.status_code,
                response=response.json() if response.text else None,
            )
        elif response.status_code == 429:
            raise RateLimitError(
                "Rate limit exceeded",
                status_code=response.status_code,
                response=response.text,
            )
        elif response.status_code >= 500:
            raise ServerError(
                "Server error",
                status_code=response.status_code,
                response=response.text,
            )
        elif not response.is_success:
            raise OpenWearablesError(
                f"Request failed with status {response.status_code}",
                status_code=response.status_code,
                response=response.text,
            )

        if response.status_code == 204:
            return None
        return response.json()

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make a synchronous HTTP request."""
        client = self._get_client()
        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = client.request(method, path, params=params, json=json)
        return self._handle_response(response)

    async def arequest(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make an asynchronous HTTP request."""
        client = self._get_async_client()
        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await client.request(method, path, params=params, json=json)
        return self._handle_response(response)

    def close(self) -> None:
        """Close the synchronous client."""
        if self._client:
            self._client.close()
            self._client = None

    async def aclose(self) -> None:
        """Close the asynchronous client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
