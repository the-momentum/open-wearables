"""Shared fixtures for MCP tests.

The tool modules import a module-level `client` singleton from
`app.services.api_client`. Tests configure that singleton with a
predictable base URL + key so `pytest-httpx` can intercept requests,
and restore the original values after each test.
"""

from collections.abc import Iterator

import pytest

from app.services import api_client as api_client_module


@pytest.fixture(autouse=True)
def _configure_singleton_client() -> Iterator[None]:
    """Point the singleton client at a predictable test host with a dummy key."""
    client = api_client_module.client
    original_key = client._api_key
    original_url = client.base_url

    client._api_key = "test_key"
    client.base_url = "https://api.test.com"
    try:
        yield
    finally:
        client._api_key = original_key
        client.base_url = original_url
