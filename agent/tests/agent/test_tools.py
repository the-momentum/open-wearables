"""Tests for agent tool functions (date tools and OW data tools)."""

from collections.abc import Iterator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.agent.tools.date_tools import get_current_week, get_today_date
from app.agent.tools.ow_tools import (
    get_body_composition,
    get_heart_rate_timeseries,
    get_recent_activity,
    get_recent_sleep,
    get_recovery_data,
    get_sleep_events,
    get_user_profile,
    get_workouts,
    lookup_user,
)


def _make_ctx(user_id: UUID | None = None) -> MagicMock:
    """Return a minimal mock RunContext[HealthAgentDeps] for tool unit tests."""
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.user_id = user_id if user_id is not None else uuid4()
    return ctx


# ---------------------------------------------------------------------------
# Date tools
# ---------------------------------------------------------------------------


class TestGetTodayDate:
    def test_returns_iso_format_string(self) -> None:
        result = get_today_date()

        # Should be parseable as a date
        parsed = date.fromisoformat(result)
        assert parsed == date.today()

    def test_returns_string(self) -> None:
        assert isinstance(get_today_date(), str)


class TestGetCurrentWeek:
    def test_returns_start_and_end_keys(self) -> None:
        result = get_current_week()

        assert "start" in result
        assert "end" in result

    def test_start_is_monday(self) -> None:
        result = get_current_week()

        start = date.fromisoformat(result["start"])
        assert start.weekday() == 0  # Monday

    def test_end_is_sunday(self) -> None:
        result = get_current_week()

        end = date.fromisoformat(result["end"])
        assert end.weekday() == 6  # Sunday

    def test_end_is_six_days_after_start(self) -> None:
        result = get_current_week()

        start = date.fromisoformat(result["start"])
        end = date.fromisoformat(result["end"])
        assert (end - start).days == 6


# ---------------------------------------------------------------------------
# OW tools
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> Iterator[MagicMock]:
    with patch("app.agent.tools.ow_tools.ow_client") as mock:
        mock.search_users = AsyncMock(
            return_value={
                "items": [
                    {
                        "id": "user-uuid-1",
                        "first_name": "Jan",
                        "last_name": "Kowalski",
                        "email": "jan@example.com",
                    }
                ],
                "total": 1,
            }
        )
        mock.get_user_profile = AsyncMock(return_value={"id": "abc", "first_name": "Alice"})
        mock.get_body_summary = AsyncMock(return_value={"slow_changing": {"weight_kg": 70}})
        mock.get_activity_summaries = AsyncMock(return_value={"data": [{"steps": 8000}]})
        mock.get_sleep_summaries = AsyncMock(return_value={"data": [{"duration_minutes": 450}]})
        mock.get_recovery_summaries = AsyncMock(return_value={"data": []})
        mock.get_workout_events = AsyncMock(return_value={"data": []})
        mock.get_sleep_events = AsyncMock(return_value={"data": []})
        mock.get_timeseries = AsyncMock(return_value={"data": []})
        yield mock


class TestGetUserProfile:
    async def test_calls_ow_client_and_returns_string(self, mock_client: MagicMock) -> None:
        result = await get_user_profile(_make_ctx())

        assert "Alice" in result
        mock_client.get_user_profile.assert_called_once()

    async def test_returns_error_string_on_exception(self) -> None:
        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.get_user_profile = AsyncMock(side_effect=Exception("network error"))
            result = await get_user_profile(_make_ctx())

        assert "Error" in result


class TestGetBodyComposition:
    async def test_calls_ow_client(self, mock_client: MagicMock) -> None:
        result = await get_body_composition(_make_ctx())

        assert isinstance(result, str)
        mock_client.get_body_summary.assert_called_once()

    async def test_returns_error_on_failure(self) -> None:
        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.get_body_summary = AsyncMock(side_effect=RuntimeError("oops"))
            result = await get_body_composition(_make_ctx())

        assert "Error" in result


class TestGetRecentActivity:
    async def test_calls_activity_summaries(self, mock_client: MagicMock) -> None:
        result = await get_recent_activity(_make_ctx(), days=7)

        assert isinstance(result, str)
        mock_client.get_activity_summaries.assert_called_once()

    async def test_clamps_days_to_maximum(self, mock_client: MagicMock) -> None:
        await get_recent_activity(_make_ctx(), days=999)

        call_args = mock_client.get_activity_summaries.call_args
        start_date = date.fromisoformat(call_args[0][1])
        end_date = date.fromisoformat(call_args[0][2])
        assert (end_date - start_date).days <= 30

    async def test_clamps_days_to_minimum(self, mock_client: MagicMock) -> None:
        await get_recent_activity(_make_ctx(), days=0)

        call_args = mock_client.get_activity_summaries.call_args
        start_date = date.fromisoformat(call_args[0][1])
        end_date = date.fromisoformat(call_args[0][2])
        assert (end_date - start_date).days >= 1


class TestGetRecentSleep:
    async def test_calls_sleep_summaries(self, mock_client: MagicMock) -> None:
        result = await get_recent_sleep(_make_ctx(), days=7)

        assert isinstance(result, str)
        mock_client.get_sleep_summaries.assert_called_once()


class TestGetRecoveryData:
    async def test_calls_recovery_summaries(self, mock_client: MagicMock) -> None:
        result = await get_recovery_data(_make_ctx(), days=7)

        assert isinstance(result, str)
        mock_client.get_recovery_summaries.assert_called_once()


class TestGetWorkouts:
    async def test_calls_workout_events(self, mock_client: MagicMock) -> None:
        result = await get_workouts(_make_ctx(), days=14)

        assert isinstance(result, str)
        mock_client.get_workout_events.assert_called_once()

    async def test_clamps_days_to_60(self, mock_client: MagicMock) -> None:
        await get_workouts(_make_ctx(), days=100)

        call_args = mock_client.get_workout_events.call_args
        start_date = date.fromisoformat(call_args[0][1])
        end_date = date.fromisoformat(call_args[0][2])
        assert (end_date - start_date).days <= 60


class TestGetSleepEvents:
    async def test_calls_sleep_events(self, mock_client: MagicMock) -> None:
        result = await get_sleep_events(_make_ctx(), days=7)

        assert isinstance(result, str)
        mock_client.get_sleep_events.assert_called_once()

    async def test_clamps_days_to_14(self, mock_client: MagicMock) -> None:
        await get_sleep_events(_make_ctx(), days=100)

        call_args = mock_client.get_sleep_events.call_args
        start_date = date.fromisoformat(call_args[0][1])
        end_date = date.fromisoformat(call_args[0][2])
        assert (end_date - start_date).days <= 14


class TestGetHeartRateTimeseries:
    async def test_calls_timeseries_with_heart_rate_type(self, mock_client: MagicMock) -> None:
        result = await get_heart_rate_timeseries(_make_ctx(), hours=24)

        assert isinstance(result, str)
        mock_client.get_timeseries.assert_called_once()
        call_args = mock_client.get_timeseries.call_args
        assert "heart_rate" in call_args[1].get("types", call_args[0][3] if len(call_args[0]) > 3 else [])

    async def test_clamps_hours_to_168(self, mock_client: MagicMock) -> None:
        await get_heart_rate_timeseries(_make_ctx(), hours=9999)

        # Should not raise; clamped internally
        mock_client.get_timeseries.assert_called_once()


# ---------------------------------------------------------------------------
# lookup_user
# ---------------------------------------------------------------------------


class TestLookupUser:
    async def test_returns_formatted_list_when_users_found(self, mock_client: MagicMock) -> None:
        result = await lookup_user(_make_ctx(), name="Jan")

        assert "Jan" in result
        assert "Kowalski" in result
        assert "user-uuid-1" in result
        mock_client.search_users.assert_called_once_with("Jan")

    async def test_returns_no_users_message_when_empty(self) -> None:
        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.search_users = AsyncMock(return_value={"items": [], "total": 0})
            result = await lookup_user(_make_ctx(), name="Unknown")

        assert "No users found" in result
        assert "Unknown" in result

    async def test_returns_error_string_on_exception(self) -> None:
        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.search_users = AsyncMock(side_effect=Exception("network error"))
            result = await lookup_user(_make_ctx(), name="Alice")

        assert "Error" in result

    async def test_handles_missing_optional_fields(self) -> None:
        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.search_users = AsyncMock(return_value={"items": [{"id": "some-uuid"}], "total": 1})
            result = await lookup_user(_make_ctx(), name="x")

        assert "some-uuid" in result
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# target_user_id override behaviour
# ---------------------------------------------------------------------------


class TestTargetUserId:
    async def test_get_user_profile_uses_target_user_id(self, mock_client: MagicMock) -> None:
        target = uuid4()
        ctx = _make_ctx()  # ctx has its own user_id

        await get_user_profile(ctx, target_user_id=target)

        called_with = mock_client.get_user_profile.call_args[0][0]
        assert called_with == target
        assert called_with != ctx.deps.user_id

    async def test_get_user_profile_falls_back_to_ctx_user_id(self, mock_client: MagicMock) -> None:
        ctx = _make_ctx()

        await get_user_profile(ctx, target_user_id=None)

        called_with = mock_client.get_user_profile.call_args[0][0]
        assert called_with == ctx.deps.user_id

    async def test_get_recent_sleep_uses_target_user_id(self, mock_client: MagicMock) -> None:
        target = uuid4()
        ctx = _make_ctx()

        await get_recent_sleep(ctx, days=7, target_user_id=target)

        called_with = mock_client.get_sleep_summaries.call_args[0][0]
        assert called_with == target
        assert called_with != ctx.deps.user_id

    async def test_get_recent_activity_uses_target_user_id(self, mock_client: MagicMock) -> None:
        target = uuid4()
        ctx = _make_ctx()

        await get_recent_activity(ctx, days=7, target_user_id=target)

        called_with = mock_client.get_activity_summaries.call_args[0][0]
        assert called_with == target

    async def test_returns_error_when_no_user_id_available(self) -> None:
        ctx = _make_ctx()
        ctx.deps.user_id = None  # explicitly unset so _resolve_user_id raises

        with patch("app.agent.tools.ow_tools.ow_client") as mock:
            mock.get_user_profile = AsyncMock(return_value={})
            result = await get_user_profile(ctx, target_user_id=None)

        assert "Error" in result
