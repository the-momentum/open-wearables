"""Open Wearables data-retrieval tools for the reasoning agent.

Each function catches all exceptions and returns a human-readable error string
so the LLM always receives a response (never an unhandled exception).

user_id is resolved from RunContext deps — the model never needs to supply it
for the logged-in user. Use target_user_id to query a different user.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from pydantic_ai import RunContext

from app.agent.deps import HealthAgentDeps
from app.integrations.ow_backend import ow_client

logger = logging.getLogger(__name__)


def _resolve_user_id(
    ctx: RunContext[HealthAgentDeps],
    target_user_id: UUID | None,
) -> UUID:
    if target_user_id is not None:
        return target_user_id
    if ctx.deps.user_id is None:
        raise ValueError("user_id is not set in agent dependencies")
    return ctx.deps.user_id


def _iso(d: date) -> str:
    return d.isoformat()


def _date_range(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return _iso(start), _iso(end)


async def lookup_user(ctx: RunContext[HealthAgentDeps], name: str) -> str:
    """Search for users by name or email and return their UUIDs.

    Use this when the user refers to a person by name (e.g. "how is Alice
    sleeping?", "compare Bob and Alice", "show Jan Kowalski's workouts").
    Pass a partial or full first name, last name, or email fragment.

    Do NOT call this if the user already provided a UUID — pass it directly
    as target_user_id to the relevant data tool.

    For comparison queries involving two people by name, call this tool once
    per person, then use the returned UUIDs as target_user_id in subsequent
    data tool calls.

    Args:
        name: Partial or full name / email to search for.

    Returns a list of matching users with their IDs. Pick the correct UUID
    and pass it as target_user_id to the relevant data tool.
    """
    try:
        data = await ow_client.search_users(name)
        results = data.get("items", [])
        if not results:
            return f'No users found matching "{name}".'
        lines = [f'Found {len(results)} user(s) matching "{name}":']
        for u in results:
            first = u.get("first_name") or ""
            last = u.get("last_name") or ""
            email = u.get("email") or "no email"
            uid = u.get("id", "unknown")
            lines.append(f"  {first} {last} <{email}> — id: {uid}")
        return "\n".join(lines)
    except Exception:
        logger.exception("lookup_user failed")
        return "Error searching for users."


async def get_user_profile(
    ctx: RunContext[HealthAgentDeps],
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve the user's basic profile: name, email, birth date, sex, and gender.

    Args:
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        data = await ow_client.get_user_profile(_resolve_user_id(ctx, target_user_id))
        return str(data)
    except Exception:
        logger.exception("get_user_profile failed")
        return "Error fetching user profile."


async def get_body_composition(
    ctx: RunContext[HealthAgentDeps],
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve body composition metrics: weight, height, BMI, body fat, \
muscle mass, age, resting heart rate, and HRV.

    Args:
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        data = await ow_client.get_body_summary(_resolve_user_id(ctx, target_user_id))
        return str(data)
    except Exception:
        logger.exception("get_body_composition failed")
        return "Error fetching body composition."


async def get_recent_activity(
    ctx: RunContext[HealthAgentDeps],
    days: int = 7,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve daily activity summaries: steps, distance, calories, active \
minutes, and floors climbed.

    Args:
        days: Number of past days to include (default 7, max 30).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_activity_summaries(_resolve_user_id(ctx, target_user_id), start, end)
        return str(data)
    except Exception:
        logger.exception("get_recent_activity failed")
        return "Error fetching activity data."


async def get_recent_sleep(
    ctx: RunContext[HealthAgentDeps],
    days: int = 7,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve daily sleep summaries: duration, efficiency, sleep stages \
(deep/light/REM/awake), average heart rate, HRV, and SpO2.

    Args:
        days: Number of past days to include (default 7, max 30).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_sleep_summaries(_resolve_user_id(ctx, target_user_id), start, end)
        return str(data)
    except Exception:
        logger.exception("get_recent_sleep failed")
        return "Error fetching sleep data."


async def get_recovery_data(
    ctx: RunContext[HealthAgentDeps],
    days: int = 7,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve daily recovery metrics: resting heart rate, HRV SDNN, SpO2, \
and sleep efficiency.

    Use this to assess how well the user is recovering between training
    sessions or over time.

    Args:
        days: Number of past days to include (default 7, max 30).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_recovery_summaries(_resolve_user_id(ctx, target_user_id), start, end)
        return str(data)
    except Exception:
        logger.exception("get_recovery_data failed")
        return "Error fetching recovery data."


async def get_workouts(
    ctx: RunContext[HealthAgentDeps],
    days: int = 14,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve recent workout sessions: type, duration, calories burned, \
and heart rate stats.

    Args:
        days: Number of past days to include (default 14, max 60).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        days = min(max(1, days), 60)
        start, end = _date_range(days)
        data = await ow_client.get_workout_events(_resolve_user_id(ctx, target_user_id), start, end)
        return str(data)
    except Exception:
        logger.exception("get_workouts failed")
        return "Error fetching workout data."


async def get_sleep_events(
    ctx: RunContext[HealthAgentDeps],
    days: int = 7,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve detailed sleep session records including stage intervals and timing.

    Use this when the user asks for granular sleep breakdown rather than
    daily averages.

    Args:
        days: Number of past days to include (default 7, max 14).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        days = min(max(1, days), 14)
        start, end = _date_range(days)
        data = await ow_client.get_sleep_events(_resolve_user_id(ctx, target_user_id), start, end)
        return str(data)
    except Exception:
        logger.exception("get_sleep_events failed")
        return "Error fetching sleep events."


async def get_heart_rate_timeseries(
    ctx: RunContext[HealthAgentDeps],
    hours: int = 24,
    target_user_id: UUID | None = None,
) -> str:
    """Retrieve heart rate time-series data for the past N hours at 1-hour \
resolution.

    Use this to show HR trends throughout the day or identify elevated HR
    periods.

    Args:
        hours: Number of past hours to include (default 24, max 168 = 7 days).
        target_user_id: UUID of the user to query. Leave as None (default) to
            query the logged-in user. Set this to query a different user —
            either a UUID the user typed directly, or one returned by
            lookup_user. For comparisons, call this tool twice: once per user
            with their respective UUIDs.
    """
    try:
        from datetime import datetime, timezone

        hours = min(max(1, hours), 168)
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=hours)
        data = await ow_client.get_timeseries(
            _resolve_user_id(ctx, target_user_id),
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            types=["heart_rate"],
            resolution="1hour",
        )
        return str(data)
    except Exception:
        logger.exception("get_heart_rate_timeseries failed")
        return "Error fetching HR timeseries."


OW_TOOLS: list = [
    lookup_user,
    get_user_profile,
    get_body_composition,
    get_recent_activity,
    get_recent_sleep,
    get_recovery_data,
    get_workouts,
    get_sleep_events,
    get_heart_rate_timeseries,
]
