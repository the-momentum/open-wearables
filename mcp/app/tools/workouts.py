"""MCP tool for querying workout records."""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.services.api_client import client

logger = logging.getLogger(__name__)


def _format_duration_seconds(seconds: int | None) -> str | None:
    """Format duration in seconds to human-readable string."""
    if seconds is None:
        return None
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _format_distance(meters: float | None) -> str | None:
    """Format distance in meters to km with unit."""
    if meters is None:
        return None
    km = meters / 1000
    if km >= 10:
        return f"{km:.1f} km"
    return f"{km:.2f} km"


def _format_pace(sec_per_km: int | None) -> str | None:
    """Format pace in seconds per km to 'X:XX min/km' format."""
    if sec_per_km is None:
        return None
    minutes = sec_per_km // 60
    seconds = sec_per_km % 60
    return f"{minutes}:{seconds:02d} min/km"


def _format_datetime(dt_str: str | None) -> tuple[str | None, str | None]:
    """Extract date and time from ISO datetime string.

    Returns:
        Tuple of (date_str, time_str) in formats YYYY-MM-DD and HH:MM
    """
    if not dt_str:
        return None, None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        return None, None


async def get_workouts(
    user_id: str | None = None,
    user_name: str | None = None,
    days: int = 7,
    workout_type: str | None = None,
) -> dict:
    """
    Get workout records for a user over the last X days.

    This tool retrieves workout sessions including type, duration, distance,
    heart rate, and other metrics recorded by wearable devices.

    Args:
        user_id: UUID of the user. If not provided, will attempt to find user by name
                 or auto-select if only one user exists.
        user_name: First name of the user to search for. Used if user_id is not provided.
                   Example: "John" will match users with "John" in their first name.
        days: Number of days to look back. Default is 7. Maximum is 90.
        workout_type: Optional filter by workout type. Common values:
                      "running", "cycling", "swimming", "strength_training",
                      "walking", "hiking", "yoga", "rowing", "elliptical".

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The date range queried (start, end)
        - workouts: List of workout records with details
        - summary: Aggregate statistics (total count, by type, totals)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2025-01-07", "end": "2025-01-14"},
            "workouts": [
                {
                    "date": "2025-01-13",
                    "type": "running",
                    "name": "Morning Run",
                    "start_time": "07:15",
                    "end_time": "08:02",
                    "duration_seconds": 2820,
                    "duration_formatted": "47m",
                    "distance_meters": 7500,
                    "distance_formatted": "7.50 km",
                    "calories_kcal": 520,
                    "avg_heart_rate_bpm": 145,
                    "max_heart_rate_bpm": 172,
                    "pace_formatted": "6:16 min/km",
                    "elevation_gain_meters": 85,
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_workouts": 5,
                "workouts_by_type": {"running": 3, "cycling": 2},
                "total_duration_seconds": 12500,
                "total_duration_formatted": "3h 28m",
                "total_distance_meters": 45000,
                "total_distance_formatted": "45.00 km",
                "total_calories_kcal": 2100
            }
        }

    Notes for LLMs:
        - Use the workout_type parameter to filter results (e.g., "show me my runs")
        - Distance and pace may be null for non-distance workouts (strength training, yoga)
        - Calories may be null if not tracked by the device
        - Duration is provided in both seconds (for calculations) and formatted string
        - The 'source' field indicates which wearable provided the data (garmin, whoop, etc.)
        - If user_id is not provided and multiple users exist, this will return
          an error with available_users list. Use list_users to discover users first.
    """
    # Validate days parameter
    days = min(max(1, days), 90)

    try:
        # Step 1: Resolve user ID (same pattern as sleep tool)
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

        # Step 2: Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Step 3: Fetch workout data
        workouts_response = await client.get_workouts(
            user_id=resolved_user["id"],
            start_date=start_str,
            end_date=end_str,
            workout_type=workout_type,
        )

        records_data = workouts_response.get("data", [])

        # Step 4: Transform records
        workouts = []
        workout_types: list[str] = []
        total_duration = 0
        total_distance = 0.0
        total_calories = 0.0

        for record in records_data:
            # Extract date and time from start_time
            start_dt = record.get("start_time")
            end_dt = record.get("end_time")
            date_str, start_time_str = _format_datetime(start_dt)
            _, end_time_str = _format_datetime(end_dt)

            # Get duration
            duration = record.get("duration_seconds")
            if duration:
                total_duration += duration

            # Get distance
            distance = record.get("distance_meters")
            if distance:
                total_distance += distance

            # Get calories
            calories = record.get("calories_kcal")
            if calories:
                total_calories += calories

            # Track workout types
            wtype = record.get("type")
            if wtype:
                workout_types.append(wtype)

            # Get source provider
            source = record.get("source", {})
            source_provider = source.get("provider") if isinstance(source, dict) else source

            workouts.append(
                {
                    "date": date_str,
                    "type": wtype,
                    "name": record.get("name"),
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "duration_seconds": duration,
                    "duration_formatted": _format_duration_seconds(duration),
                    "distance_meters": distance,
                    "distance_formatted": _format_distance(distance),
                    "calories_kcal": calories,
                    "avg_heart_rate_bpm": record.get("avg_heart_rate_bpm"),
                    "max_heart_rate_bpm": record.get("max_heart_rate_bpm"),
                    "pace_formatted": _format_pace(record.get("avg_pace_sec_per_km")),
                    "elevation_gain_meters": record.get("elevation_gain_meters"),
                    "source": source_provider,
                }
            )

        # Step 5: Calculate summary statistics
        workouts_by_type = dict(Counter(workout_types))

        summary = {
            "total_workouts": len(workouts),
            "workouts_by_type": workouts_by_type if workouts_by_type else None,
            "total_duration_seconds": total_duration if total_duration > 0 else None,
            "total_duration_formatted": _format_duration_seconds(total_duration) if total_duration > 0 else None,
            "total_distance_meters": total_distance if total_distance > 0 else None,
            "total_distance_formatted": _format_distance(total_distance) if total_distance > 0 else None,
            "total_calories_kcal": round(total_calories) if total_calories > 0 else None,
        }

        return {
            "user": resolved_user,
            "period": {"start": start_str, "end": end_str},
            "workouts": workouts,
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"API error in get_workouts: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_workouts: {e}")
        return {"error": f"Failed to fetch workouts: {e}"}
