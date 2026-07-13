"""Tests for the typed exception hierarchy raised by `OpenWearablesClient`.

Mirrors the pattern used by `sdk/python/tests/`: `pytest` + `pytest-asyncio`
+ `pytest-httpx`, with mocked HTTP responses.
"""

import pytest
from pytest_httpx import HTTPXMock

from app.services.api_client import OpenWearablesClient
from app.services.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    OpenWearablesError,
)


@pytest.fixture
def api_client() -> OpenWearablesClient:
    """Fresh client wired to a predictable base URL + dummy key."""
    client = OpenWearablesClient()
    client._api_key = "test_key"
    client.base_url = "https://api.test.com"
    return client


async def test_request_raises_authentication_error_on_401(
    api_client: OpenWearablesClient,
    httpx_mock: HTTPXMock,
) -> None:
    """A 401 from the backend surfaces as `AuthenticationError`."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.test.com/api/v1/users?limit=100",
        status_code=401,
    )

    with pytest.raises(AuthenticationError, match="Invalid API key"):
        await api_client.get_users()


async def test_request_raises_not_found_error_on_404(
    api_client: OpenWearablesClient,
    httpx_mock: HTTPXMock,
) -> None:
    """A 404 from the backend surfaces as `NotFoundError`."""
    user_id = "00000000-0000-0000-0000-000000000000"
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{user_id}",
        status_code=404,
    )

    with pytest.raises(NotFoundError, match="Resource not found"):
        await api_client.get_user(user_id)


async def test_request_raises_configuration_error_when_key_missing() -> None:
    """A request with no API key raises `ConfigurationError` before hitting the network."""
    client = OpenWearablesClient()
    client._api_key = ""

    with pytest.raises(ConfigurationError, match="OPEN_WEARABLES_API_KEY is not configured"):
        await client.get_users()


def test_typed_errors_inherit_from_base() -> None:
    """Every typed error is catchable via the `OpenWearablesError` base class."""
    assert issubclass(AuthenticationError, OpenWearablesError)
    assert issubclass(NotFoundError, OpenWearablesError)
    assert issubclass(ConfigurationError, OpenWearablesError)
