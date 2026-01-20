"""Tests for the OpenWearables client."""

import pytest

from open_wearables import OpenWearables


def test_client_requires_api_key():
    """Test that client requires an API key."""
    with pytest.raises(ValueError, match="api_key is required"):
        OpenWearables(api_key="")


def test_client_creates_users_resource():
    """Test that client creates users resource."""
    client = OpenWearables(api_key="test_key")
    assert client.users is not None


def test_client_context_manager():
    """Test that client works as context manager."""
    with OpenWearables(api_key="test_key") as client:
        assert client.users is not None


@pytest.mark.asyncio
async def test_client_async_context_manager():
    """Test that client works as async context manager."""
    async with OpenWearables(api_key="test_key") as client:
        assert client.users is not None
