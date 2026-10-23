"""MCP tools for querying sleep records."""

import logging

from fastmcp import FastMCP

from app.services.api_client import client
from app.services.exceptions import NotFoundError, OpenWearablesError
from app.utils import normalize_datetime

logger = logging.getLogger(__name__)

# Create router for sleep-related tools
sleep_router = FastMCP(name="Sleep Tools")


@sleep_router.tool
async def get_sleep_summary(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Get daily sleep summaries for a user within a date range.

    This tool retrieves daily sleep summaries including start time, end time,
    duration, and the sleep-stage totals the wearable reports (awake, light, deep
    and REM minutes), plus the other per-day metrics the backend returns.

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
        - records: List of sleep records, one per day, carrying every field the
          backend returns (stages, efficiency_percent, time_in_bed_minutes,
          total_duration_minutes, sessions, naps, HRV/SpO2, ...). See the values
          passed through below; fields the provider does not report are null.
        - summary: Aggregate statistics (avg_duration, total_nights, etc.)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {"start": "2026-01-05", "end": "2026-01-12"},
            "records": [
                {
                    "date": "2026-01-11",
                    "start_datetime": "2026-01-11T23:15:00+00:00",
                    "end_datetime": "2026-01-12T07:30:00+00:00",
                    "zone_offset": "+00:00",
                    "duration_minutes": 495,
                    "total_duration_minutes": 520,
                    "time_in_bed_minutes": 540,
                    "efficiency_percent": 91.7,
                    "stages": {
                        "awake_minutes": 15,
                        "light_minutes": 250,
                        "deep_minutes": 90,
                        "rem_minutes": 155
                    },
                    "interruptions_count": 3,
                    "nap_count": 1,
                    "nap_duration_minutes": 25,
                    "sessions": [{"start_time": "...", "end_time": "...", "duration_minutes": 495, "is_nap": false}],
                    "avg_heart_rate_bpm": 58,
                    "avg_hrv_sdnn_ms": 45.2,
                    "avg_spo2_percent": 96.5,
                    "source": "whoop"
                }
            ],
            "summary": {
                "total_nights": 7,
                "nights_with_data": 6,
                "avg_duration_minutes": 465,
                "min_duration_minutes": 360,
                "max_duration_minutes": 540
            }
        }

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - Calculate dates based on user queries:
          "last week" → start_date = 7 days ago, end_date = today
          "January 2026" → start_date = "2026-01-01", end_date = "2026-01-31"
        - Duration is in minutes.
        - The 'date' field is based on end_datetime (when the user woke up), not when they fell asleep.
        - start_datetime and end_datetime are full ISO 8601 timestamps. Sleep typically
          spans midnight, so end_datetime is often the day after start_datetime.
        - 'stages' holds the night's totals in minutes when the wearable reports sleep
          stages; it is null for providers that do not. Use it to answer deep/REM/light
          questions.
        - For the individual stage segments (the order the stages occurred in) use the
          sleep-stage intervals from the events API; this tool returns per-day totals only.
        - The 'source' field indicates which wearable provided the data (whoop, garmin, etc.)
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
        except NotFoundError as e:
            return {"error": f"User not found: {user_id}", "details": str(e)}

        # Fetch sleep data
        sleep_response = await client.get_sleep_summaries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        records_data = sleep_response.get("data", [])

        # Transform records
        records = []
        durations = []

        for record in records_data:
            duration = record.get("duration_minutes")
            if duration is not None:
                durations.append(duration)

            # Carry the whole summary through instead of listing fields: the endpoint
            # already returns the stage totals and the other per-day metrics, and
            # rebuilding the record here is what silently dropped them.
            record_out = dict(record)
            source = record_out.pop("source", None)
            record_out["date"] = str(record_out.get("date"))
            record_out["start_datetime"] = normalize_datetime(record_out.pop("start_time", None))
            record_out["end_datetime"] = normalize_datetime(record_out.pop("end_time", None))
            record_out["source"] = source.get("provider") if isinstance(source, dict) else source
            records.append(record_out)

        # Calculate summary statistics
        summary = {
            "total_nights": len(records),
            "nights_with_data": len(durations),
            "avg_duration_minutes": None,
            "min_duration_minutes": None,
            "max_duration_minutes": None,
        }

        if durations:
            avg = sum(durations) / len(durations)
            summary.update(
                {
                    "avg_duration_minutes": round(avg),
                    "min_duration_minutes": min(durations),
                    "max_duration_minutes": max(durations),
                }
            )

        return {
            "user": user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    except OpenWearablesError as e:
        logger.error(f"API error in get_sleep_summary: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_sleep_summary: {e}")
        return {"error": f"Failed to fetch sleep summary: {e}"}
