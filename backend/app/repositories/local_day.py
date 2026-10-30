from datetime import date, datetime, time, timedelta, timezone

# A local day reaches up to 14 hours either side of its UTC date.
OFFSET_REACH = timedelta(hours=14)


def utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time(), timezone.utc)


def sample_day_sql(alias: str = "series_sample") -> str:
    """The local day of a series_sample row in SQL; a missing offset reads as UTC, as every reader does."""
    return f"(({alias}.recorded_at AT TIME ZONE 'UTC') + coalesce({alias}.zone_offset, '+00:00')::interval)::date"


def every_series_type_sql(alias: str = "series_sample") -> str:
    """Every series type, spelled out: with it the (source, type, time) index bounds a source's time range on
    PostgreSQL 17, which cannot skip over the type and would otherwise read the source's whole history."""
    return f"{alias}.series_type_definition_id = ANY(ARRAY(SELECT id FROM series_type_definition))"
