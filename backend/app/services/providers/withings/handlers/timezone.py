"""Convert Withings local dates and IANA zones to stored UTC instants and offsets.

Withings is the only provider that sends an IANA zone *name* alongside an epoch
or a local date, so loading the zone is provider-local; formatting the resulting
offset is not, and goes through ``app.utils.dates.offset_to_iso``.
"""

from datetime import date as date_type
from datetime import datetime, timezone
from logging import Logger
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.utils.dates import offset_to_iso
from app.utils.structured_logging import log_structured


def _load_zone(
    timezone_name: str | None,
    logger: Logger,
    *,
    action: str,
    **context: Any,
) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        log_structured(
            logger,
            "warning",
            "Invalid Withings timezone; falling back to UTC semantics",
            provider="withings",
            action=action,
            timezone=timezone_name,
            **context,
        )
        return None


def _offset_of(moment: datetime) -> str | None:
    """Render an aware datetime's UTC offset, the way Oura's workouts do."""
    offset = moment.utcoffset()
    return offset_to_iso(int(offset.total_seconds())) if offset is not None else None


def zone_offset_at(
    timezone_name: str | None,
    utc_instant: datetime,
    logger: Logger,
    *,
    action: str,
    **context: Any,
) -> str | None:
    """Return the zone's canonical offset at an aware UTC instant."""
    zone = _load_zone(timezone_name, logger, action=action, **context)
    if zone is None:
        return None
    return _offset_of(utc_instant.astimezone(zone))


def local_day_start(
    local_date: date_type,
    timezone_name: str | None,
    logger: Logger,
    *,
    action: str,
    **context: Any,
) -> tuple[datetime, str | None]:
    """Resolve a local calendar day to its UTC instant and offset."""
    midnight = datetime(local_date.year, local_date.month, local_date.day)
    zone = _load_zone(timezone_name, logger, action=action, **context)
    if zone is None:
        return midnight.replace(tzinfo=timezone.utc), None
    local_midnight = midnight.replace(tzinfo=zone)
    return local_midnight.astimezone(timezone.utc), _offset_of(local_midnight)
