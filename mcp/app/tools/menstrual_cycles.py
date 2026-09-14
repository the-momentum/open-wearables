"""MCP tools for querying menstrual cycle records."""

import logging
from datetime import date, datetime

from fastmcp import FastMCP

from app.services.api_client import client
from app.services.exceptions import NotFoundError, OpenWearablesError
from app.utils import normalize_datetime

logger = logging.getLogger(__name__)

# Safety ceiling for cursor pagination: 10 pages x 100 records covers decades of cycles.
_MAX_PAGES = 10

# Create router for menstrual cycle tools
menstrual_cycles_router = FastMCP(name="Menstrual Cycle Tools")


def _starts_after(start_time: str | None, end_date: str) -> bool:
    """True when a record's cycle start date falls after the requested end date."""
    if not start_time:
        return False
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00")).date()
        end = date.fromisoformat(end_date)
    except ValueError:
        return False
    return start > end


@menstrual_cycles_router.tool
async def get_menstrual_cycles(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Get menstrual cycle records for a user within a date range.

    This tool retrieves menstrual cycle tracking data including the current
    cycle day, cycle phase, period length, cycle length, and predicted
    fertile window from wearable devices.

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
        - records: List of menstrual cycle records
        - summary: Aggregate statistics (avg_cycle_length_days, phase_types, etc.)
        - truncated: True when the pagination safety ceiling was hit and older
          records were left out

    Example response:
        {
            "user": {"id": "uuid-1", "first_name": "Jane", "last_name": "Doe"},
            "period": {"start": "2026-01-01", "end": "2026-01-28"},
            "records": [
                {
                    "id": "uuid-cycle-1",
                    "start_datetime": "2026-01-05T00:00:00+00:00",
                    "end_datetime": "2026-02-02T00:00:00+00:00",
                    "day_in_cycle": 14,
                    "cycle_length": 28,
                    "period_length": 5,
                    "current_phase": 2,
                    "current_phase_type": "ovulation",
                    "length_of_current_phase": 4,
                    "days_until_next_phase": 2,
                    "predicted_cycle_length": 28,
                    "is_predicted_cycle": false,
                    "fertile_window_start": 12,
                    "length_of_fertile_window": 6,
                    "has_specified_cycle_length": true,
                    "has_specified_period_length": true,
                    "pregnancy_snapshot": null,
                    "last_updated_at": "2026-01-18T06:30:00+00:00",
                    "source": "garmin"
                }
            ],
            "summary": {
                "total_records": 4,
                "predicted_records": 1,
                "avg_cycle_length_days": 28.5,
                "avg_period_length_days": 5.0,
                "phase_types": {"menstruation": 1, "follicular": 1, "ovulation": 1, "luteal": 1},
                "has_pregnancy_data": false,
                "latest": {
                    "start_datetime": "2026-01-05T00:00:00+00:00",
                    "day_in_cycle": 14,
                    "current_phase_type": "ovulation",
                    "days_until_next_phase": 2,
                    "is_predicted_cycle": false
                }
            },
            "truncated": false
        }

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - Calculate dates based on user queries:
          "last month" -> start_date = 30 days ago, end_date = today
          "this year" -> start_date = first of year, end_date = today
        - Records are filtered by cycle start date. Cycles starting after
          end_date are excluded, so a historical window does not pick up
          predicted future cycles. The cycle currently in progress is included
          when it started inside the window, even though it ends after
          end_date.
        - summary.latest is the most recent logged cycle when one exists, and
          falls back to the most recent predicted cycle otherwise.
        - day_in_cycle counts from 1 on the first day of the menstrual period.
        - current_phase_type is a lowercase string: "menstruation" (also reported
          as "menstrual" by some providers), "follicular", "ovulation", "luteal",
          or "pregnancy". Treat other values as unclassified.
        - All length fields are in days. fertile_window_start is a day number
          within the cycle, so the fertile window spans fertile_window_start to
          fertile_window_start + length_of_fertile_window - 1.
        - is_predicted_cycle true means the provider predicted this cycle instead
          of the user logging it.
        - The 'source' field indicates which provider supplied the data. Menstrual
          cycle data is currently ingested from Garmin devices.
        - This is sensitive health data. Present it factually and only to the
          extent the user asked for.
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
        except NotFoundError as e:
            return {"error": f"User not found: {user_id}", "details": str(e)}

        # Walk cursor pagination until exhausted or the safety ceiling is hit
        records_data: list[dict] = []
        cursor: str | None = None
        truncated = False
        for _ in range(_MAX_PAGES):
            cycles_response = await client.get_menstrual_cycles(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                cursor=cursor,
            )
            records_data.extend(cycles_response.get("data", []))
            cursor = (cycles_response.get("pagination") or {}).get("next_cursor")
            if not cursor:
                break
        else:
            truncated = True

        # Transform records
        records = []
        cycle_lengths = []
        period_lengths = []
        phase_types: dict[str, int] = {}
        predicted_count = 0
        has_pregnancy_data = False
        latest = None
        latest_start = None
        latest_predicted = False

        for record in records_data:
            start_time = record.get("start_time")

            # The backend leaves end_date unbounded so predicted cycles stay
            # visible; apply the requested upper bound here.
            if _starts_after(start_time, end_date):
                continue

            cycle_length = record.get("cycle_length")
            period_length = record.get("period_length")
            phase_type = record.get("current_phase_type")
            pregnancy_snapshot = record.get("pregnancy_snapshot")

            if cycle_length is not None:
                cycle_lengths.append(cycle_length)
            if period_length is not None:
                period_lengths.append(period_length)
            if phase_type:
                phase_types[phase_type] = phase_types.get(phase_type, 0) + 1
            if record.get("is_predicted_cycle"):
                predicted_count += 1
            if pregnancy_snapshot:
                has_pregnancy_data = True

            source = record.get("source", {})
            transformed = {
                "id": str(record.get("id")),
                "start_datetime": normalize_datetime(start_time),
                "end_datetime": normalize_datetime(record.get("end_time")),
                "day_in_cycle": record.get("day_in_cycle"),
                "cycle_length": cycle_length,
                "period_length": period_length,
                "current_phase": record.get("current_phase"),
                "current_phase_type": phase_type,
                "length_of_current_phase": record.get("length_of_current_phase"),
                "days_until_next_phase": record.get("days_until_next_phase"),
                "predicted_cycle_length": record.get("predicted_cycle_length"),
                "is_predicted_cycle": record.get("is_predicted_cycle"),
                "fertile_window_start": record.get("fertile_window_start"),
                "length_of_fertile_window": record.get("length_of_fertile_window"),
                "has_specified_cycle_length": record.get("has_specified_cycle_length"),
                "has_specified_period_length": record.get("has_specified_period_length"),
                "pregnancy_snapshot": pregnancy_snapshot,
                "last_updated_at": normalize_datetime(record.get("last_updated_at")),
                "source": source.get("provider") if isinstance(source, dict) else source,
            }
            records.append(transformed)

            # Track the most recent logged cycle; a logged cycle always wins over
            # a predicted one, which can start in the future.
            is_predicted = bool(record.get("is_predicted_cycle"))
            if start_time and (
                latest_start is None
                or (latest_predicted and not is_predicted)
                or (latest_predicted == is_predicted and start_time > latest_start)
            ):
                latest_start = start_time
                latest_predicted = is_predicted
                latest = {
                    "start_datetime": transformed["start_datetime"],
                    "day_in_cycle": transformed["day_in_cycle"],
                    "current_phase_type": transformed["current_phase_type"],
                    "days_until_next_phase": transformed["days_until_next_phase"],
                    "is_predicted_cycle": transformed["is_predicted_cycle"],
                }

        # Calculate summary statistics
        summary = {
            "total_records": len(records),
            "predicted_records": predicted_count,
            "avg_cycle_length_days": (round(sum(cycle_lengths) / len(cycle_lengths), 1) if cycle_lengths else None),
            "avg_period_length_days": (round(sum(period_lengths) / len(period_lengths), 1) if period_lengths else None),
            "phase_types": phase_types if phase_types else None,
            "has_pregnancy_data": has_pregnancy_data,
            "latest": latest,
        }

        return {
            "user": user,
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
            "truncated": truncated,
        }

    except OpenWearablesError as e:
        logger.error(f"API error in get_menstrual_cycles: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_menstrual_cycles: {e}")
        return {"error": f"Failed to fetch menstrual cycles: {e}"}
