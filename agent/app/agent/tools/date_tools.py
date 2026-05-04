"""Date utility tools available to the reasoning agent."""

from datetime import date, timedelta


def get_today_date() -> str:
    """Return today's date as an ISO string (YYYY-MM-DD).

    Use this whenever you need to anchor relative time expressions like
    'yesterday', 'last week', or 'this month'.
    """
    return date.today().isoformat()


def get_current_week() -> dict[str, str]:
    """Return the start (Monday) and end (Sunday) dates of the current week as ISO strings.

    Returns a dict with keys 'start' and 'end'.
    """
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return {"start": start.isoformat(), "end": end.isoformat()}


DATE_TOOLS: list = [get_today_date, get_current_week]
