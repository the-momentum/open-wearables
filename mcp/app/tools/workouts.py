"""MCP tools for querying workout records."""

import logging
from datetime import datetime

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for workout-related tools
workouts_router = FastMCP(name="Workout Tools")


def _format_duration(seconds: int | None) -> str | None:
    """Format duration in seconds to human-readable string."""
    if seconds is None:
        return None
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _format_distance(meters: float | None) -> str | None:
    """Format distance in meters to human-readable string."""
    if meters is None:
        return None
    km = meters / 1000
    if km >= 1:
        return f"{km:.2f} km"
    return f"{int(meters)} m"


def _format_pace(seconds_per_km: int | None) -> str | None:
    """Format pace in seconds per km to human-readable string."""
    if seconds_per_km is None:
        return None
    minutes = seconds_per_km // 60
    secs = seconds_per_km % 60
    return f"{minutes}:{secs:02d} /km"


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


@workouts_router.tool
async def list_workouts(
    user_id: str,
    start_date: str,
    end_date: str,
    workout_type: str | None = None,
) -> dict:
    """
    Get workout records for a user within a date range.

    This tool retrieves workout sessions including type, duration, distance,
    calories, and heart rate data (if available from the wearable device).

    Args:
        user_id: UUID of the user. Use list_users to discover available users.
        start_date: Start date in YYYY-MM-DD format.
                    Example: "2025-01-01"
        end_date: End date in YYYY-MM-DD format.
                  Example: "2025-01-07"
        workout_type: Optional filter by workout type.
                      Examples: "running", "cycling", "swimming", "strength_training",
                      "walking", "hiking", "yoga", "hiit"

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The date range queried (start, end)
        - records: List of workout records with details
        - summary: Aggregate statistics (total_workouts, total_duration, etc.)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2025-01-05", "end": "2025-01-12"},
            "records": [
                {
                    "id": "uuid-workout-1",
                    "type": "running",
                    "start_datetime": "2025-01-11T07:00:00+00:00",
                    "end_datetime": "2025-01-11T07:45:00+00:00",
                    "duration_seconds": 2700,
                    "duration_formatted": "45m",
                    "distance_meters": 7500.0,
                    "distance_formatted": "7.50 km",
                    "calories_kcal": 520.0,
                    "avg_heart_rate_bpm": 145,
                    "max_heart_rate_bpm": 172,
                    "elevation_gain_meters": 85.0,
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_workouts": 5,
                "workouts_with_distance": 4,
                "total_duration_seconds": 12600,
                "total_duration_formatted": "3h 30m",
                "total_distance_meters": 28500.0,
                "total_distance_formatted": "28.50 km",
                "total_calories_kcal": 2100.0,
                "avg_duration_seconds": 2520,
                "avg_duration_formatted": "42m",
                "workout_types": {"running": 3, "cycling": 2}
            }
        }

    Notes for LLMs:
        - Call list_users first to get the user_id.
        - Calculate dates based on user queries:
          "last week" -> start_date = 7 days ago, end_date = today
          "this month" -> start_date = first of month, end_date = today
        - Use the workout_type filter to narrow down results (e.g., "show my runs").
        - Duration is in seconds. Use duration_formatted for human-readable output.
        - Distance is in meters. Use distance_formatted for human-readable output.
        - The 'source' field indicates which wearable provided the data (garmin, whoop, etc.)
        - Common workout types: running, cycling, swimming, strength_training, walking,
          hiking, yoga, hiit, rowing, elliptical, pilates
    """
    try:
        # Fetch user details
        try:
            user_data = await client.get_user(user_id)
            user = {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            }
        except ValueError as e:
            return {"error": f"User not found: {user_id}", "details": str(e)}

        # Fetch workout data
        workouts_response = await client.get_workouts(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            record_type=workout_type,
        )

        records_data = workouts_response.get("data", [])

        # Transform records
        records = []
        durations = []
        distances = []
        calories = []
        workout_types: dict[str, int] = {}

        for record in records_data:
            duration = record.get("duration_seconds")
            distance = record.get("distance_meters")
            cals = record.get("calories_kcal")
            w_type = record.get("type", "unknown")

            if duration is not None:
                durations.append(duration)
            if distance is not None:
                distances.append(distance)
            if cals is not None:
                calories.append(cals)

            # Count workout types
            workout_types[w_type] = workout_types.get(w_type, 0) + 1

            source = record.get("source", {})
            records.append(
                {
                    "id": str(record.get("id")),
                    "type": w_type,
                    "start_datetime": _normalize_datetime(record.get("start_time")),
                    "end_datetime": _normalize_datetime(record.get("end_time")),
                    "duration_seconds": duration,
                    "duration_formatted": _format_duration(duration),
                    "distance_meters": distance,
                    "distance_formatted": _format_distance(distance),
                    "calories_kcal": cals,
                    "avg_heart_rate_bpm": record.get("avg_heart_rate_bpm"),
                    "max_heart_rate_bpm": record.get("max_heart_rate_bpm"),
                    "avg_pace_sec_per_km": record.get("avg_pace_sec_per_km"),
                    "avg_pace_formatted": _format_pace(record.get("avg_pace_sec_per_km")),
                    "elevation_gain_meters": record.get("elevation_gain_meters"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        # Calculate summary statistics
        total_duration = sum(durations) if durations else 0
        total_distance = sum(distances) if distances else 0
        total_cals = sum(calories) if calories else 0

        summary = {
            "total_workouts": len(records),
            "workouts_with_distance": len(distances),
            "total_duration_seconds": total_duration,
            "total_duration_formatted": _format_duration(total_duration) if total_duration else None,
            "total_distance_meters": total_distance if distances else None,
            "total_distance_formatted": _format_distance(total_distance) if distances else None,
            "total_calories_kcal": round(total_cals, 1) if calories else None,
            "avg_duration_seconds": round(total_duration / len(durations)) if durations else None,
            "avg_duration_formatted": _format_duration(round(total_duration / len(durations))) if durations else None,
            "workout_types": workout_types if workout_types else None,
        }

        return {
            "user": user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"API error in list_workouts: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in list_workouts: {e}")
        return {"error": f"Failed to fetch workout records: {e}"}
