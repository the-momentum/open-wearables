"""Tests that MCP tool handlers translate typed client errors into the
documented error-envelope shape instead of bubbling the exception up.

Each tool has two error paths worth covering:
- inner `NotFoundError` from the user-lookup block -> "User not found" envelope
- outer `OpenWearablesError` from the downstream resource fetch -> generic error envelope
"""

from collections.abc import Awaitable, Callable

import pytest
from pytest_httpx import HTTPXMock

from app.tools.activity import get_activity_summary
from app.tools.menstrual_cycles import get_menstrual_cycles
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
    """`get_users` translates a backend 401 into the documented empty-envelope shape."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.test.com/api/v1/users?limit=10",
        status_code=401,
    )

    result = await get_users()

    assert result["users"] == []
    assert result["total"] == 0
    assert "error" in result


@pytest.mark.parametrize(
    "tool",
    [
        pytest.param(get_activity_summary, id="activity"),
        pytest.param(get_menstrual_cycles, id="menstrual_cycles"),
        pytest.param(get_sleep_summary, id="sleep"),
        pytest.param(get_workout_events, id="workouts"),
    ],
)
async def test_summary_tools_return_user_not_found_envelope_on_404(
    tool: Callable[..., Awaitable[dict]],
    httpx_mock: HTTPXMock,
) -> None:
    """Summary tools turn a 404 on user lookup into the 'User not found' envelope (inner except block)."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        status_code=404,
    )

    result = await tool(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert result["error"] == f"User not found: {USER_ID}"
    assert "details" in result


async def test_get_timeseries_returns_user_not_found_envelope_on_404(httpx_mock: HTTPXMock) -> None:
    """`get_timeseries` turns a 404 on user lookup into the 'User not found' envelope."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        status_code=404,
    )

    result = await get_timeseries(
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
    """Downstream 401 (after user lookup succeeds) surfaces via the generic error envelope, not 'User not found'."""
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

    result = await get_activity_summary(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert "error" in result
    assert "Invalid API key" in result["error"]
    assert not result["error"].startswith("User not found")


async def test_get_menstrual_cycles_transforms_records_and_summary(httpx_mock: HTTPXMock) -> None:
    """`get_menstrual_cycles` maps backend records and aggregates cycle statistics."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        json=USER_PAYLOAD,
    )
    httpx_mock.add_response(
        method="GET",
        url=(
            f"https://api.test.com/api/v1/users/{USER_ID}/events/menstrual-cycles"
            "?start_date=2026-01-01&end_date=2026-02-28&limit=100"
        ),
        json={
            "data": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "start_time": "2026-01-05T00:00:00Z",
                    "end_time": "2026-02-02T00:00:00Z",
                    "zone_offset": None,
                    "source": {"provider": "garmin", "source": "Connect", "device": None, "device_type": None},
                    "current_phase": 2,
                    "current_phase_type": "ovulation",
                    "day_in_cycle": 14,
                    "cycle_length": 28,
                    "predicted_cycle_length": 28,
                    "is_predicted_cycle": False,
                    "period_length": 5,
                    "fertile_window_start": 12,
                    "length_of_fertile_window": 6,
                    "pregnancy_snapshot": None,
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "start_time": "2026-02-02T00:00:00Z",
                    "end_time": "2026-03-04T00:00:00Z",
                    "zone_offset": None,
                    "source": {"provider": "garmin", "source": "Connect", "device": None, "device_type": None},
                    "current_phase": 1,
                    "current_phase_type": "menstruation",
                    "day_in_cycle": 3,
                    "cycle_length": 30,
                    "predicted_cycle_length": 30,
                    "is_predicted_cycle": True,
                    "period_length": 6,
                    "pregnancy_snapshot": None,
                },
                {
                    # Predicted cycle starting after end_date: must be excluded
                    "id": "33333333-3333-3333-3333-333333333333",
                    "start_time": "2026-03-04T00:00:00Z",
                    "end_time": "2026-04-03T00:00:00Z",
                    "zone_offset": None,
                    "source": {"provider": "garmin", "source": "Connect", "device": None, "device_type": None},
                    "current_phase": None,
                    "current_phase_type": None,
                    "day_in_cycle": None,
                    "cycle_length": None,
                    "predicted_cycle_length": 30,
                    "is_predicted_cycle": True,
                    "period_length": 6,
                    "pregnancy_snapshot": None,
                },
            ],
            "pagination": {"next_cursor": None, "previous_cursor": None, "total_count": 2},
            "metadata": {},
        },
    )

    result = await get_menstrual_cycles(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-02-28",
    )

    assert result["user"]["id"] == USER_ID
    # The record starting after end_date is dropped
    assert len(result["records"]) == 2
    assert result["records"][0]["source"] == "garmin"
    assert result["records"][0]["start_datetime"] == "2026-01-05T00:00:00+00:00"
    assert result["truncated"] is False

    summary = result["summary"]
    assert summary["total_records"] == 2
    assert summary["predicted_records"] == 1
    assert summary["avg_cycle_length_days"] == 29.0
    assert summary["avg_period_length_days"] == 5.5
    assert summary["phase_types"] == {"ovulation": 1, "menstruation": 1}
    assert summary["has_pregnancy_data"] is False
    # The most recent record is predicted, so latest falls back to the logged cycle
    assert summary["latest"]["day_in_cycle"] == 14
    assert summary["latest"]["current_phase_type"] == "ovulation"
    assert summary["latest"]["is_predicted_cycle"] is False


async def test_get_menstrual_cycles_walks_pagination(httpx_mock: HTTPXMock) -> None:
    """`get_menstrual_cycles` follows next_cursor until the last page."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        json=USER_PAYLOAD,
    )
    record_template = {
        "start_time": "2026-01-05T00:00:00Z",
        "end_time": "2026-02-02T00:00:00Z",
        "source": {"provider": "garmin"},
        "cycle_length": 28,
        "period_length": 5,
        "current_phase_type": "luteal",
        "is_predicted_cycle": False,
    }
    httpx_mock.add_response(
        method="GET",
        url=(
            f"https://api.test.com/api/v1/users/{USER_ID}/events/menstrual-cycles"
            "?start_date=2026-01-01&end_date=2026-02-28&limit=100"
        ),
        json={
            "data": [{"id": "11111111-1111-1111-1111-111111111111", **record_template}],
            "pagination": {"next_cursor": "page2", "previous_cursor": None, "total_count": 2},
            "metadata": {},
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=(
            f"https://api.test.com/api/v1/users/{USER_ID}/events/menstrual-cycles"
            "?start_date=2026-01-01&end_date=2026-02-28&limit=100&cursor=page2"
        ),
        json={
            "data": [{"id": "22222222-2222-2222-2222-222222222222", **record_template}],
            "pagination": {"next_cursor": None, "previous_cursor": "prev_page1", "total_count": 2},
            "metadata": {},
        },
    )

    result = await get_menstrual_cycles(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-02-28",
    )

    assert len(result["records"]) == 2
    assert result["summary"]["total_records"] == 2
    assert result["truncated"] is False


async def test_get_menstrual_cycles_handles_empty_data(httpx_mock: HTTPXMock) -> None:
    """`get_menstrual_cycles` returns an empty records list and null aggregates when there is no data."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.test.com/api/v1/users/{USER_ID}",
        json=USER_PAYLOAD,
    )
    httpx_mock.add_response(
        method="GET",
        url=(
            f"https://api.test.com/api/v1/users/{USER_ID}/events/menstrual-cycles"
            "?start_date=2026-01-01&end_date=2026-01-07&limit=100"
        ),
        json={
            "data": [],
            "pagination": {"next_cursor": None, "previous_cursor": None, "total_count": 0},
            "metadata": {},
        },
    )

    result = await get_menstrual_cycles(
        user_id=USER_ID,
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert result["records"] == []
    assert result["summary"]["total_records"] == 0
    assert result["summary"]["avg_cycle_length_days"] is None
    assert result["summary"]["phase_types"] is None
    assert result["summary"]["latest"] is None
