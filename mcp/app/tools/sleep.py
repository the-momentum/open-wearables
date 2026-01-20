"""MCP tools for querying sleep records."""

import logging
from datetime import datetime

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for sleep-related tools
sleep_router = FastMCP(name="Sleep Tools")


def _format_duration(minutes: int | None) -> str | None:
    """Format duration in minutes to human-readable string."""
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _normalize_datetime(dt_str: str | None) -> str | None:
    """Normalize datetime string to ISO 8601 format."""
    if not dt_str:
        return None
    try:
        # Parse and normalize to consistent ISO format
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, AttributeError):
        return dt_str


@sleep_router.tool
async def get_sleep_records(
    user_id: str | None = None,
    user_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Get sleep records for a user within a date range.

    This tool retrieves daily sleep summaries including start time, end time,
    duration, and sleep stages (if available from the wearable device).

    Args:
        user_id: UUID of the user. If not provided, will attempt to find user by name
                 or list available users if multiple exist.
        user_name: First name of the user to search for. Used if user_id is not provided.
                   Example: "John" will match users with "John" in their first name.
        start_date: Start date in YYYY-MM-DD format. Required.
                    Example: "2025-01-01"
        end_date: End date in YYYY-MM-DD format. Required.
                  Example: "2025-01-07"

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The date range queried (start, end)
        - records: List of sleep records with date, start_datetime, end_datetime, duration
        - summary: Aggregate statistics (avg_duration, total_nights, etc.)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2025-01-05", "end": "2025-01-12"},
            "records": [
                {
                    "date": "2025-01-11",
                    "start_datetime": "2025-01-11T23:15:00+00:00",
                    "end_datetime": "2025-01-12T07:30:00+00:00",
                    "duration_minutes": 495,
                    "duration_formatted": "8h 15m",
                    "source": "whoop"
                }
            ],
            "summary": {
                "total_nights": 7,
                "nights_with_data": 6,
                "avg_duration_minutes": 465,
                "avg_duration_formatted": "7h 45m",
                "min_duration_minutes": 360,
                "max_duration_minutes": 540
            }
        }

    Notes for LLMs:
        - Both start_date and end_date are required. Calculate dates based on user queries:
          "last week" → start_date = 7 days ago, end_date = today
          "January 2025" → start_date = "2025-01-01", end_date = "2025-01-31"
        - If user_id is not provided and multiple users exist, this will return
          an error with available_users list. Use list_users to discover users first.
        - Duration is in minutes. Use duration_formatted for human-readable output.
        - The 'date' field is based on end_datetime (when the user woke up), not when they fell asleep.
        - start_datetime and end_datetime are full ISO 8601 timestamps. Sleep typically
          spans midnight, so end_datetime is often the day after start_datetime.
        - The 'source' field indicates which wearable provided the data (whoop, garmin, etc.)
        - For questions about sleep quality, check if stages data is available in the backend.
    """
    # Validate date parameters
    if not start_date or not end_date:
        return {
            "error": "Both start_date and end_date are required (YYYY-MM-DD format).",
            "example": {"start_date": "2025-01-01", "end_date": "2025-01-07"},
        }

    try:
        # Step 1: Resolve user ID
        resolved_user = None

        if user_id:
            # Fetch user details to confirm they exist
            try:
                user_data = await client.get_user(user_id)
                resolved_user = {
                    "id": str(user_data.get("id")),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                }
            except ValueError as e:
                return {"error": f"User not found: {user_id}", "details": str(e)}

        elif user_name:
            # Search for user by name
            users_response = await client.get_users(search=user_name)
            users = users_response.get("items", [])

            if len(users) == 0:
                return {
                    "error": f"No user found with name '{user_name}'",
                    "suggestion": "Use list_users to see all available users.",
                }
            elif len(users) == 1:
                user = users[0]
                resolved_user = {
                    "id": str(user.get("id")),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                }
            else:
                # Multiple matches - return options
                return {
                    "error": f"Multiple users match '{user_name}'. Please specify user_id.",
                    "matches": [
                        {
                            "id": str(u.get("id")),
                            "first_name": u.get("first_name"),
                            "last_name": u.get("last_name"),
                        }
                        for u in users
                    ],
                }

        else:
            # No user specified - check if there's only one user
            users_response = await client.get_users()
            users = users_response.get("items", [])

            if len(users) == 0:
                return {"error": "No users found. Create a user first via the Open Wearables API."}
            elif len(users) == 1:
                user = users[0]
                resolved_user = {
                    "id": str(user.get("id")),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                }
            else:
                # Multiple users - need to specify
                return {
                    "error": "Multiple users available. Please specify user_id or user_name.",
                    "available_users": [
                        {
                            "id": str(u.get("id")),
                            "first_name": u.get("first_name"),
                            "last_name": u.get("last_name"),
                        }
                        for u in users[:10]  # Limit to first 10
                    ],
                    "total_users": len(users),
                }

        # Step 2: Fetch sleep data
        sleep_response = await client.get_sleep_summaries(
            user_id=resolved_user["id"],
            start_date=start_date,
            end_date=end_date,
        )

        records_data = sleep_response.get("data", [])

        # Step 4: Transform records
        records = []
        durations = []

        for record in records_data:
            duration = record.get("duration_minutes")
            if duration is not None:
                durations.append(duration)

            source = record.get("source", {})
            records.append(
                {
                    "date": str(record.get("date")),
                    "start_datetime": _normalize_datetime(record.get("start_time")),
                    "end_datetime": _normalize_datetime(record.get("end_time")),
                    "duration_minutes": duration,
                    "duration_formatted": _format_duration(duration),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        # Step 5: Calculate summary statistics
        summary = {
            "total_nights": len(records),
            "nights_with_data": len(durations),
            "avg_duration_minutes": None,
            "avg_duration_formatted": None,
            "min_duration_minutes": None,
            "max_duration_minutes": None,
        }

        if durations:
            avg = sum(durations) / len(durations)
            summary.update(
                {
                    "avg_duration_minutes": round(avg),
                    "avg_duration_formatted": _format_duration(round(avg)),
                    "min_duration_minutes": min(durations),
                    "max_duration_minutes": max(durations),
                }
            )

        return {
            "user": resolved_user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"API error in get_sleep_records: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_sleep_records: {e}")
        return {"error": f"Failed to fetch sleep records: {e}"}
