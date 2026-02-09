"""MCP tools for querying activity records."""

import logging

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for activity-related tools
activity_router = FastMCP(name="Activity Tools")


@activity_router.tool
async def get_activity_summary(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Get daily activity summaries for a user within a date range.

    This tool retrieves daily activity metrics including steps, calories,
    heart rate, distance, and intensity minutes from wearable devices.

    Args:
        user_id: UUID of the user. Use get_users to discover available users.
        start_date: Start date in YYYY-MM-DD format.
                    Example: "2026-01-01"
        end_date: End date in YYYY-MM-DD format.
                  Example: "2026-01-07"

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The date range queried (start, end)
        - records: List of daily activity records
        - summary: Aggregate statistics (avg_steps, total_calories, etc.)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2026-01-05", "end": "2026-01-12"},
            "records": [
                {
                    "date": "2026-01-11",
                    "steps": 8432,
                    "distance_meters": 6240.5,
                    "active_calories_kcal": 342.5,
                    "total_calories_kcal": 2150.0,
                    "active_minutes": 60,
                    "heart_rate": {
                        "avg_bpm": 72,
                        "max_bpm": 145,
                        "min_bpm": 52
                    },
                    "intensity_minutes": {
                        "light": 45,
                        "moderate": 30,
                        "vigorous": 15
                    },
                    "floors_climbed": 12,
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_days": 7,
                "days_with_data": 7,
                "total_steps": 58500,
                "avg_steps": 8357,
                "total_distance_meters": 43680.0,
                "total_active_calories_kcal": 2450.5,
                "total_calories_kcal": 15050.0,
                "avg_active_minutes": 55,
                "total_intensity_minutes": {
                    "light": 315,
                    "moderate": 180,
                    "vigorous": 90
                }
            }
        }

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - Calculate dates based on user queries:
          "last week" -> start_date = 7 days ago, end_date = today
          "this month" -> start_date = first of month, end_date = today
        - Steps is the most universal metric tracked by all wearables.
        - active_calories_kcal is energy burned through activity (exercise).
        - total_calories_kcal includes active calories plus basal metabolic rate.
        - intensity_minutes categorize activity by heart rate zones:
          light (zone 1-2), moderate (zone 3), vigorous (zone 4-5).
        - The 'source' field indicates which wearable provided the data (garmin, whoop, etc.)
        - Heart rate data includes daily averages, max, and resting heart rate.
        - Use the present_health_data prompt for formatting guidelines when presenting to users.
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

        # Fetch activity data
        activity_response = await client.get_activity_summaries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        records_data = activity_response.get("data", [])

        # Transform records and collect aggregates
        records = []
        steps_list = []
        distances = []
        active_calories = []
        total_calories = []
        active_minutes_list = []
        intensity_light = []
        intensity_moderate = []
        intensity_vigorous = []

        for record in records_data:
            steps = record.get("steps")
            distance = record.get("distance_meters")
            active_cal = record.get("active_calories_kcal")
            total_cal = record.get("total_calories_kcal")
            active_mins = record.get("active_minutes")
            intensity = record.get("intensity_minutes") or {}
            heart_rate = record.get("heart_rate")

            if steps is not None:
                steps_list.append(steps)
            if distance is not None:
                distances.append(distance)
            if active_cal is not None:
                active_calories.append(active_cal)
            if total_cal is not None:
                total_calories.append(total_cal)
            if active_mins is not None:
                active_minutes_list.append(active_mins)
            if intensity.get("light") is not None:
                intensity_light.append(intensity["light"])
            if intensity.get("moderate") is not None:
                intensity_moderate.append(intensity["moderate"])
            if intensity.get("vigorous") is not None:
                intensity_vigorous.append(intensity["vigorous"])

            source = record.get("source", {})
            records.append(
                {
                    "date": str(record.get("date")),
                    "steps": steps,
                    "distance_meters": distance,
                    "active_calories_kcal": active_cal,
                    "total_calories_kcal": total_cal,
                    "active_minutes": active_mins,
                    "sedentary_minutes": record.get("sedentary_minutes"),
                    "heart_rate": heart_rate,
                    "intensity_minutes": intensity if intensity else None,
                    "floors_climbed": record.get("floors_climbed"),
                    "elevation_meters": record.get("elevation_meters"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        # Calculate summary statistics
        total_steps = sum(steps_list) if steps_list else None
        total_distance = sum(distances) if distances else None

        summary = {
            "total_days": len(records),
            "days_with_data": len(steps_list),
            "total_steps": total_steps,
            "avg_steps": round(total_steps / len(steps_list)) if steps_list else None,
            "total_distance_meters": total_distance,
            "total_active_calories_kcal": round(sum(active_calories), 1) if active_calories else None,
            "total_calories_kcal": round(sum(total_calories), 1) if total_calories else None,
            "avg_active_minutes": (
                round(sum(active_minutes_list) / len(active_minutes_list)) if active_minutes_list else None
            ),
            "total_intensity_minutes": {
                "light": sum(intensity_light) if intensity_light else None,
                "moderate": sum(intensity_moderate) if intensity_moderate else None,
                "vigorous": sum(intensity_vigorous) if intensity_vigorous else None,
            }
            if (intensity_light or intensity_moderate or intensity_vigorous)
            else None,
        }

        return {
            "user": user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"API error in get_activity_summary: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_activity_summary: {e}")
        return {"error": f"Failed to fetch activity summary: {e}"}
