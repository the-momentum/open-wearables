"""MCP tools for querying workout records."""

import logging

from fastmcp import FastMCP

from app.services.api_client import client
from app.utils import normalize_datetime

logger = logging.getLogger(__name__)

# Create router for workout-related tools
workouts_router = FastMCP(name="Workout Tools")


@workouts_router.tool
async def get_workout_events(
    user_id: str,
    start_date: str,
    end_date: str,
    workout_type: str | None = None,
) -> dict:
    """
    Get workout events for a user within a date range.

    This tool retrieves discrete workout sessions including type, duration, distance,
    calories, and heart rate data (if available from the wearable device).

    Args:
        user_id: UUID of the user. Use get_users to discover available users.
        start_date: Start date in YYYY-MM-DD format.
                    Example: "2026-01-01"
        end_date: End date in YYYY-MM-DD format.
                  Example: "2026-01-07"
        workout_type: Optional filter by workout type.
                      Examples: "running", "cycling", "swimming", "strength_training",
                      "walking", "hiking", "yoga", "hiit"

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The date range queried (start, end)
        - records: List of workout events with details
        - summary: Aggregate statistics (total_workouts, total_duration, etc.)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2026-01-05", "end": "2026-01-12"},
            "records": [
                {
                    "id": "uuid-workout-1",
                    "type": "running",
                    "start_datetime": "2026-01-11T07:00:00+00:00",
                    "end_datetime": "2026-01-11T07:45:00+00:00",
                    "duration_seconds": 2700,
                    "distance_meters": 7500.0,
                    "calories_kcal": 520.0,
                    "avg_heart_rate_bpm": 145,
                    "max_heart_rate_bpm": 172,
                    "avg_pace_sec_per_km": 360,
                    "elevation_gain_meters": 85.0,
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_workouts": 5,
                "workouts_with_distance": 4,
                "total_duration_seconds": 12600,
                "total_distance_meters": 28500.0,
                "total_calories_kcal": 2100.0,
                "avg_duration_seconds": 2520,
                "workout_types": {"running": 3, "cycling": 2}
            }
        }

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - Calculate dates based on user queries:
          "last week" -> start_date = 7 days ago, end_date = today
          "this month" -> start_date = first of month, end_date = today
        - Use the workout_type filter to narrow down results (e.g., "show my runs").
        - Duration is in seconds, distance in meters, pace in seconds per km.
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
                    "start_datetime": normalize_datetime(record.get("start_time")),
                    "end_datetime": normalize_datetime(record.get("end_time")),
                    "duration_seconds": duration,
                    "distance_meters": distance,
                    "calories_kcal": cals,
                    "avg_heart_rate_bpm": record.get("avg_heart_rate_bpm"),
                    "max_heart_rate_bpm": record.get("max_heart_rate_bpm"),
                    "avg_pace_sec_per_km": record.get("avg_pace_sec_per_km"),
                    "elevation_gain_meters": record.get("elevation_gain_meters"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        # Calculate summary statistics
        total_duration = sum(durations)
        total_distance = sum(distances)
        total_cals = sum(calories)
        avg_duration = round(total_duration / len(durations)) if durations else None

        summary = {
            "total_workouts": len(records),
            "workouts_with_distance": len(distances),
            "total_duration_seconds": total_duration,
            "total_distance_meters": total_distance if distances else None,
            "total_calories_kcal": round(total_cals, 1) if calories else None,
            "avg_duration_seconds": avg_duration,
            "workout_types": workout_types if workout_types else None,
        }

        return {
            "user": user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"API error in get_workout_events: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_workout_events: {e}")
        return {"error": f"Failed to fetch workout events: {e}"}
