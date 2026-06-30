from datetime import datetime, timedelta, timezone

from pydantic import BaseModel


class WithingsNotification(BaseModel):
    """Inbound Withings notify payload (form-urlencoded, notify-only).

    Withings delivers the affected data range three ways:
    - measure categories (appli 1/2/4/44/58): ``startdate`` + ``enddate`` (unix epoch);
    - event-based categories (appli 16 activity): a single ``date`` (YYYY-MM-DD);
    - profile change (appli 46): neither — carries ``action`` instead.

    All optional; the usable window is derived by ``resolve_window``.
    """

    userid: str
    appli: int
    startdate: int | None = None
    enddate: int | None = None
    date: str | None = None
    action: str | None = None

    def resolve_window(self) -> tuple[datetime, datetime] | None:
        """Resolve the [start, end) window to fetch, or ``None`` if absent."""
        if self.startdate is not None and self.enddate is not None:
            return (
                datetime.fromtimestamp(self.startdate, tz=timezone.utc),
                datetime.fromtimestamp(self.enddate, tz=timezone.utc),
            )
        if self.date is not None:
            day = self._parse_date(self.date)
            if day is not None:
                return (day, day + timedelta(days=1))
        return None

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        """Parse ``date`` as YYYY-MM-DD, falling back to a stringified epoch."""
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return None
