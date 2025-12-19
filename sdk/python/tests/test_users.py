"""Tests for the Users resource."""

import pytest
from pytest_httpx import HTTPXMock

from open_wearables import OpenWearables


@pytest.fixture
def client():
    """Create a test client."""
    return OpenWearables(api_key="test_key", base_url="https://api.test.com")


def test_create_user(client: OpenWearables, httpx_mock: HTTPXMock):
    """Test creating a user."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.test.com/api/v1/users",
        json={
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "created_at": "2025-01-01T00:00:00Z",
            "external_user_id": "user_123",
            "email": "test@example.com",
            "first_name": None,
            "last_name": None,
        },
    )

    user = client.users.create(external_user_id="user_123", email="test@example.com")

    assert str(user.id) == "550e8400-e29b-41d4-a716-446655440000"
    assert user.external_user_id == "user_123"
    assert user.email == "test@example.com"


def test_get_user(client: OpenWearables, httpx_mock: HTTPXMock):
    """Test getting a user."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{user_id}",
        json={
            "id": user_id,
            "created_at": "2025-01-01T00:00:00Z",
            "external_user_id": "user_123",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
        },
    )

    user = client.users.get(user_id=user_id)

    assert str(user.id) == user_id
    assert user.first_name == "John"
    assert user.last_name == "Doe"


def test_list_users(client: OpenWearables, httpx_mock: HTTPXMock):
    """Test listing users."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.test.com/api/v1/users",
        json=[
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2025-01-01T00:00:00Z",
                "external_user_id": "user_1",
                "email": "user1@example.com",
                "first_name": None,
                "last_name": None,
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "created_at": "2025-01-02T00:00:00Z",
                "external_user_id": "user_2",
                "email": "user2@example.com",
                "first_name": None,
                "last_name": None,
            },
        ],
    )

    users = client.users.list()

    assert len(users) == 2
    assert users[0].external_user_id == "user_1"
    assert users[1].external_user_id == "user_2"


def test_get_workouts(client: OpenWearables, httpx_mock: HTTPXMock):
    """Test getting workouts."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{user_id}/workouts?limit=10&offset=0",
        json=[
            {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "type": "HKWorkoutActivityTypeRunning",
                "duration_seconds": "1800",
                "source_name": "Apple Watch",
                "start_datetime": "2025-01-01T08:00:00Z",
                "end_datetime": "2025-01-01T08:30:00Z",
                "statistics": [],
            },
        ],
    )

    workouts = client.users.get_workouts(user_id=user_id, limit=10, offset=0)

    assert len(workouts) == 1
    assert workouts[0].type == "HKWorkoutActivityTypeRunning"
    assert workouts[0].source_name == "Apple Watch"


@pytest.mark.asyncio
async def test_async_create_user(client: OpenWearables, httpx_mock: HTTPXMock):
    """Test creating a user asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.test.com/api/v1/users",
        json={
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "created_at": "2025-01-01T00:00:00Z",
            "external_user_id": "user_123",
            "email": "test@example.com",
            "first_name": None,
            "last_name": None,
        },
    )

    user = await client.users.acreate(external_user_id="user_123", email="test@example.com")

    assert str(user.id) == "550e8400-e29b-41d4-a716-446655440000"
    assert user.external_user_id == "user_123"

    await client.aclose()
