"""Tests that MCP tool handlers translate typed client errors into the
documented error-envelope shape instead of bubbling the exception up.

Each tool has two error paths worth covering:
- inner `NotFoundError` from the user-lookup block -> "User not found" envelope
- outer `OpenWearablesError` from the downstream resource fetch -> generic error envelope
"""

import pytest
from pytest_httpx import HTTPXMock

from app.tools.activity import get_activity_summary
from app.tools.sleep import get_sleep_summary
from app.tools.timeseries import get_timeseries
from app.tools.users import get_users
from app.tools.workouts import get_workout_events

USER_ID = "00000000-0000-0000-0000-000000000000"
USER_PAYLOAD = {
    "id": USER_ID,
    "first_name": "Test",
    "last_name": "User",
    "email": "test@example.com",
}


async def test_get_users_returns_empty_envelope_on_auth_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.test.com/api/v1/users?limit=10",
        status_code=401,
    )

    result = await get_users.fn()

    assert result["users"] == []
    assert result["total"] == 0
    assert "error" in result


@pytest.mark.parametrize(
    "tool",
    [
        pytest.param(get_activity_summary, id="activity"),
        pytest.param(get_sleep_summary, id="sleep"),
        pytest.param(get_workout_events, id="workouts"),
    ],
)
async def test_summary_tools_return_user_not_found_envelope_on_404(
    tool: object,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        status_code=404,
    )

    result = await tool.fn(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert result["error"] == f"User not found: {USER_ID}"
    assert "details" in result


async def test_get_timeseries_returns_user_not_found_envelope_on_404(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        status_code=404,
    )

    result = await get_timeseries.fn(
        user_id=USER_ID,
        start_time="2026-04-05T00:00:00Z",
        end_time="2026-04-05T23:59:59Z",
        types=["heart_rate"],
    )

    assert result["error"] == f"User not found: {USER_ID}"
    assert "details" in result


async def test_get_activity_summary_returns_generic_error_envelope_on_downstream_401(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        json=USER_PAYLOAD,
    )
    httpx_mock.add_response(
        method="GET",
        url=(
            f"https://api.test.com/api/v1/users/{USER_ID}/summaries/activity"
            "?start_date=2026-01-01&end_date=2026-01-07&limit=100"
        ),
        status_code=401,
    )

    result = await get_activity_summary.fn(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert "error" in result
    assert "Invalid API key" in result["error"]
    assert not result["error"].startswith("User not found")
