"""Main client for the Open Wearables API."""

from __future__ import annotations

from open_wearables.http import HttpClient
from open_wearables.resources import UsersResource


class OpenWearables:
    """Open Wearables API client.

    A typed, async-ready Python SDK for the Open Wearables API.

    Example:
        ```python
        from open_wearables import OpenWearables

        # Sync usage
        client = OpenWearables(api_key="ow_your_api_key")
        user = client.users.create(
            external_user_id="user_123",
            email="john@example.com"
        )
        workouts = client.users.get_workouts(user_id=user.id, limit=50)

        # Async usage
        import asyncio

        async def main():
            client = OpenWearables(api_key="ow_your_api_key")
            user = await client.users.acreate(
                external_user_id="user_123",
                email="john@example.com"
            )
            workouts = await client.users.aget_workouts(user_id=user.id, limit=50)
            await client.aclose()

        asyncio.run(main())
        ```

    Args:
        api_key: Your Open Wearables API key.
        base_url: Optional base URL for the API (defaults to https://api.openwearables.io).
        timeout: Optional request timeout in seconds (defaults to 30.0).
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        if not api_key:
            raise ValueError("api_key is required")

        self._http = HttpClient(api_key=api_key, base_url=base_url, timeout=timeout)
        self.users = UsersResource(self._http)

    def close(self) -> None:
        """Close the client and release resources."""
        self._http.close()

    async def aclose(self) -> None:
        """Close the client and release resources (async)."""
        await self._http.aclose()

    def __enter__(self) -> OpenWearables:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> OpenWearables:
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()
