"""Open Wearables data-retrieval tools for the reasoning agent.

Each function catches all exceptions and returns a human-readable error string
so the LLM always receives a response (never an unhandled exception).
"""

from __future__ import annotations

import traceback
from datetime import date, timedelta
from uuid import UUID

from app.integrations.ow_backend import ow_client


def _iso(d: date) -> str:
    return d.isoformat()


def _date_range(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return _iso(start), _iso(end)


async def get_user_profile(user_id: str) -> str:
    """Retrieve the user's basic profile: name, email, birth date, sex, and gender.

    Args:
        user_id: UUID of the user whose profile to fetch.
    """
    try:
        data = await ow_client.get_user_profile(UUID(user_id))
        return str(data)
    except Exception:
        return f"Error fetching user profile: {traceback.format_exc(limit=1)}"


async def get_body_composition(user_id: str) -> str:
    """Retrieve body composition metrics: weight, height, BMI, body fat, muscle mass, age, \
resting heart rate, and HRV.

    Args:
        user_id: UUID of the user whose body metrics to fetch.
    """
    try:
        data = await ow_client.get_body_summary(UUID(user_id))
        return str(data)
    except Exception:
        return f"Error fetching body composition: {traceback.format_exc(limit=1)}"


async def get_recent_activity(user_id: str, days: int = 7) -> str:
    """Retrieve daily activity summaries: steps, distance, calories, active minutes, and floors climbed.

    Args:
        user_id: UUID of the user.
        days: Number of past days to include (default 7, max 30).
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_activity_summaries(UUID(user_id), start, end)
        return str(data)
    except Exception:
        return f"Error fetching activity data: {traceback.format_exc(limit=1)}"


async def get_recent_sleep(user_id: str, days: int = 7) -> str:
    """Retrieve daily sleep summaries: duration, efficiency, sleep stages (deep/light/REM/awake), \
average heart rate, HRV, and SpO2.

    Args:
        user_id: UUID of the user.
        days: Number of past days to include (default 7, max 30).
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_sleep_summaries(UUID(user_id), start, end)
        return str(data)
    except Exception:
        return f"Error fetching sleep data: {traceback.format_exc(limit=1)}"


async def get_recovery_data(user_id: str, days: int = 7) -> str:
    """Retrieve daily recovery metrics: resting heart rate, HRV SDNN, SpO2, and sleep efficiency.

    Use this to assess how well the user is recovering between training sessions or over time.

    Args:
        user_id: UUID of the user.
        days: Number of past days to include (default 7, max 30).
    """
    try:
        days = min(max(1, days), 30)
        start, end = _date_range(days)
        data = await ow_client.get_recovery_summaries(UUID(user_id), start, end)
        return str(data)
    except Exception:
        return f"Error fetching recovery data: {traceback.format_exc(limit=1)}"


async def get_workouts(user_id: str, days: int = 14) -> str:
    """Retrieve recent workout sessions: type, duration, calories burned, and heart rate stats.

    Args:
        user_id: UUID of the user.
        days: Number of past days to include (default 14, max 60).
    """
    try:
        days = min(max(1, days), 60)
        start, end = _date_range(days)
        data = await ow_client.get_workout_events(UUID(user_id), start, end)
        return str(data)
    except Exception:
        return f"Error fetching workout data: {traceback.format_exc(limit=1)}"


async def get_sleep_events(user_id: str, days: int = 7) -> str:
    """Retrieve detailed sleep session records including stage intervals and timing.

    Use this when the user asks for granular sleep breakdown rather than daily averages.

    Args:
        user_id: UUID of the user.
        days: Number of past days to include (default 7, max 14).
    """
    try:
        days = min(max(1, days), 14)
        start, end = _date_range(days)
        data = await ow_client.get_sleep_events(UUID(user_id), start, end)
        return str(data)
    except Exception:
        return f"Error fetching sleep events: {traceback.format_exc(limit=1)}"


async def get_heart_rate_timeseries(user_id: str, hours: int = 24) -> str:
    """Retrieve heart rate time-series data for the past N hours at 1-hour resolution.

    Use this to show HR trends throughout the day or identify elevated HR periods.

    Args:
        user_id: UUID of the user.
        hours: Number of past hours to include (default 24, max 168 = 7 days).
    """
    try:
        from datetime import datetime, timezone

        hours = min(max(1, hours), 168)
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=hours)
        data = await ow_client.get_timeseries(
            UUID(user_id),
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            types=["heart_rate"],
            resolution="1hour",
        )
        return str(data)
    except Exception:
        return f"Error fetching HR timeseries: {traceback.format_exc(limit=1)}"


OW_TOOLS: list = [
    get_user_profile,
    get_body_composition,
    get_recent_activity,
    get_recent_sleep,
    get_recovery_data,
    get_workouts,
    get_sleep_events,
    get_heart_rate_timeseries,
]
