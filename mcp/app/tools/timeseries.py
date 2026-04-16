"""MCP tools for querying granular time-series samples."""

import logging
from typing import Any

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for time-series tools
timeseries_router = FastMCP(name="Timeseries Tools")

# Hard ceiling on pages walked per tool call to protect the backend
# and keep responses bounded. 100 pages * 100 samples = 10k samples.
_MAX_PAGES = 100


@timeseries_router.tool
async def get_timeseries(
    user_id: str,
    start_time: str,
    end_time: str,
    types: list[str],
    resolution: str = "raw",
) -> dict:
    """
    Get granular time-series samples for a user within a time range.

    Time-series data is the raw/downsampled sample stream underlying the
    higher-level summaries (activity, sleep, workouts). Use this tool when
    the user asks about a metric that does NOT have a dedicated summary
    tool (e.g. weight, SpO2, blood glucose, respiratory rate, HRV), or
    when they need finer-grained data than daily averages.

    Args:
        user_id: UUID of the user. Use get_users to discover available users.
        start_time: Start of the window in ISO-8601 format.
                    Example: "2026-04-05T00:00:00Z"
        end_time: End of the window in ISO-8601 format.
                  Example: "2026-04-05T23:59:59Z"
        types: List of SeriesType codes to include. Common values:
               - "heart_rate", "resting_heart_rate", "walking_heart_rate_average"
               - "heart_rate_variability_sdnn", "heart_rate_variability_rmssd"
               - "oxygen_saturation", "respiratory_rate"
               - "blood_glucose", "blood_pressure_systolic", "blood_pressure_diastolic"
               - "weight", "body_fat_percentage", "body_mass_index"
               - "steps", "active_energy", "basal_energy", "distance"
        resolution: One of "raw", "1min", "5min", "15min", "1hour".
                    Default "raw" returns every sample as stored; higher
                    resolutions downsample server-side. Prefer "1min" or
                    coarser for multi-day windows to keep response size
                    bounded.

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The time window queried (start, end, resolution)
        - records: List of samples, each {timestamp, type, value, unit, source}
        - summary: Per-type aggregates (count, avg, min, max)
        - truncated: True if pagination hit the safety ceiling (rare)

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
            "period": {
                "start": "2026-04-05T00:00:00Z",
                "end": "2026-04-05T23:59:59Z",
                "resolution": "1min"
            },
            "records": [
                {
                    "timestamp": "2026-04-05T08:15:00+00:00",
                    "type": "heart_rate",
                    "value": 68,
                    "unit": "bpm",
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_samples": 1433,
                "by_type": {
                    "heart_rate": {"count": 1433, "avg": 98, "min": 48, "max": 167}
                }
            },
            "truncated": false
        }

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - `types` must be a list even for a single metric: ["heart_rate"].
        - Multi-day queries at resolution="raw" can return tens of thousands
          of samples. Prefer "1min" or coarser for anything longer than a
          day unless the user explicitly asks for raw data.
        - For a single day's heart-rate average, prefer get_activity_summary
          when it's available — it's cheaper. Use this tool when:
          (a) activity summary is missing or has null heart_rate, or
          (b) the user wants intraday detail (peaks, zones, a specific hour).
        - Values are returned in the unit the provider supplied (e.g.
          heart_rate in "bpm", weight in "kg", oxygen_saturation in "%").
          Do unit conversions client-side when presenting to the user.
        - The `source` field indicates which wearable produced the sample
          (garmin, whoop, apple_health, etc.) and may differ across samples
          in the same response when a user has multiple connected devices.
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

        # Walk cursor pagination until exhausted or safety ceiling hit.
        records: list[dict[str, Any]] = []
        cursor: str | None = None
        truncated = False
        for _ in range(_MAX_PAGES):
            response = await client.get_timeseries(
                user_id=user_id,
                start_time=start_time,
                end_time=end_time,
                types=types,
                resolution=resolution,
                cursor=cursor,
            )
            for sample in response.get("data", []):
                source = sample.get("source", {})
                records.append(
                    {
                        "timestamp": str(sample.get("timestamp")) if sample.get("timestamp") else None,
                        "type": sample.get("type"),
                        "value": sample.get("value"),
                        "unit": sample.get("unit"),
                        "source": source.get("provider") if isinstance(source, dict) else source,
                    }
                )
            cursor = (response.get("pagination") or {}).get("next_cursor")
            if not cursor:
                break
        else:
            truncated = True

        # Per-type aggregates
        by_type: dict[str, dict[str, Any]] = {}
        for rec in records:
            series_type = rec["type"]
            value = rec["value"]
            if series_type is None or value is None:
                continue
            bucket = by_type.setdefault(
                series_type,
                {"count": 0, "sum": 0.0, "min": value, "max": value},
            )
            bucket["count"] += 1
            bucket["sum"] += value
            if value < bucket["min"]:
                bucket["min"] = value
            if value > bucket["max"]:
                bucket["max"] = value

        summary_by_type = {
            series_type: {
                "count": bucket["count"],
                "avg": round(bucket["sum"] / bucket["count"], 2) if bucket["count"] else None,
                "min": bucket["min"],
                "max": bucket["max"],
            }
            for series_type, bucket in by_type.items()
        }

        return {
            "user": user,
            "period": {"start": start_time, "end": end_time, "resolution": resolution},
            "records": records,
            "summary": {
                "total_samples": len(records),
                "by_type": summary_by_type,
            },
            "truncated": truncated,
        }

    except ValueError as e:
        logger.error(f"API error in get_timeseries: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_timeseries: {e}")
        return {"error": f"Failed to fetch time-series samples: {e}"}
