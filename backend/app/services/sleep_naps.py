"""Flag the naps of providers that don't report them (#938).

A nap is a sleep of 15 min to under 3 h that starts between 06:00 and 20:00 local time and is more than the
merge gap away from the main sleep (the longest) of its day and of the next day. Days are local wake dates,
as in the sleep summary. Sleep without a zone offset has no known start hour, so it has to be more than 4 h
from those main sleeps instead.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from app.config import settings
from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import DbSession
from app.models import DataSource, EventRecord, SleepDetails
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.local_day import utc_midnight
from app.schemas.enums import ProviderName
from app.utils.dates import iso_to_timezone, local_date

# Their sleep comes without a nap flag (the mobile SDK has none); other providers' flag is kept as they send it
NAP_INFERRED_PROVIDERS: frozenset[ProviderName] = frozenset(
    {
        *(ProviderName(provider) for provider in SDK_PROVIDERS),
        ProviderName.SENSORBIO,
        ProviderName.ULTRAHUMAN,
        ProviderName.WITHINGS,
    }
)
# Less sleep than this hardly makes a nap; Oura's minimum too
NAP_MIN_SLEEP = timedelta(minutes=15)
# 3 h of sleep or more is never a nap: Oura and Garmin draw the line here, and Apple stages sleep from here on
NAP_MAX_SLEEP = timedelta(hours=3)
# Sleep that starts at night belongs to a night, even when it's short
NAP_START_HOURS = range(6, 20)
# Without a zone offset the start hour isn't known, so a nap has to be further from the night than a night-time
# awakening lasts (insomnia, segmented sleep)
NAP_GAP_WITHOUT_ZONE = timedelta(hours=4)


@dataclass(frozen=True)
class SleepWindow:
    id: UUID
    start: datetime
    end: datetime
    zone_offset: str | None
    asleep: timedelta

    @property
    def wake_date(self) -> date:
        return local_date(self.end, self.zone_offset)

    @property
    def could_be_nap(self) -> bool:
        """Its sleep fits a nap and, when its zone offset gives the start hour, it starts in the daytime."""
        if not NAP_MIN_SLEEP <= self.asleep < NAP_MAX_SLEEP:
            return False
        if self.zone_offset is None:
            # No start hour to check; find_naps asks it for NAP_GAP_WITHOUT_ZONE instead
            return True
        return self.start.astimezone(iso_to_timezone(self.zone_offset)).hour in NAP_START_HOURS


def _gap(a: SleepWindow, b: SleepWindow) -> timedelta:
    return max(a.start - b.end, b.start - a.end, timedelta(0))


def find_naps(sessions: Sequence[SleepWindow]) -> set[UUID]:
    """The naps among one data source's sessions."""
    by_day: dict[date, list[SleepWindow]] = defaultdict(list)
    for session in sessions:
        by_day[session.wake_date].append(session)
    # A day's main sleep is its longest, the earlier one on a tie
    mains = {day: min(group, key=lambda s: (-s.asleep, s.start)) for day, group in by_day.items()}
    merge_gap = timedelta(minutes=settings.sleep_end_gap_minutes)
    naps: set[UUID] = set()
    for day, group in by_day.items():
        # Sleep within the merge gap of a night belongs to it, an early start of the next night included
        nights = [main for main in (mains[day], mains.get(day + timedelta(days=1))) if main is not None]
        for session in group:
            limit = merge_gap if session.zone_offset is not None else max(merge_gap, NAP_GAP_WITHOUT_ZONE)
            if (
                session is not mains[day]
                and session.could_be_nap
                and all(_gap(session, night) > limit for night in nights)
            ):
                naps.add(session.id)
    return naps


_data_sources = DataSourceRepository(DataSource)
_event_records = EventRecordRepository(EventRecord)


@dataclass(frozen=True)
class NapChange:
    record_id: UUID
    is_nap: bool
    wake_date: date


def _window(record: EventRecord, details: SleepDetails | None) -> SleepWindow:
    """The session with its time asleep, else its length, as the sleep summary reads it."""
    minutes = details.sleep_total_duration_minutes if details is not None else None
    asleep = timedelta(minutes=minutes) if minutes is not None else timedelta(seconds=record.duration_seconds or 0)
    return SleepWindow(record.id, record.start_datetime, record.end_datetime, record.zone_offset, asleep)


def reclassify_naps(
    db_session: DbSession,
    data_source_id: UUID,
    wake_dates: set[date] | None,
    *,
    dry_run: bool = False,
) -> list[NapChange]:
    """Re-flag a data source's naps around the given local wake dates.

    None re-flags the whole history and an empty set nothing. A day's naps depend on its own and the next day's
    main sleep, so a write on day D re-flags D-1 to D+1. Returns the flags that changed (not written in a dry
    run); a provider that flags naps keeps its flags. Flushes first, so the caller's pending sessions count.
    """
    data_source = _data_sources.get(db_session, data_source_id)
    if data_source is None or data_source.provider not in NAP_INFERRED_PROVIDERS:
        return []
    if wake_dates is None:
        first = last = None
        rows = _event_records.get_source_sleep_records(db_session, data_source_id)
    elif not wake_dates:
        return []
    else:
        first, last = min(wake_dates) - timedelta(days=1), max(wake_dates) + timedelta(days=1)
        # The day after `last` gives its main sleep; a day either side covers any zone offset
        rows = _event_records.get_source_sleep_records(
            db_session, data_source_id, utc_midnight(first - timedelta(days=1)), utc_midnight(last + timedelta(days=3))
        )
    windows = {record.id: _window(record, details) for record, details in rows}
    naps = find_naps(list(windows.values()))

    changes: list[NapChange] = []
    flags: list[tuple[SleepDetails, bool]] = []
    for record, details in rows:
        if details is None:
            continue
        window = windows[record.id]
        if first is not None and last is not None and not first <= window.wake_date <= last:
            continue
        is_nap = record.id in naps
        if bool(details.is_nap) != is_nap:
            changes.append(NapChange(record.id, is_nap, window.wake_date))
            flags.append((details, is_nap))
    if flags and not dry_run:
        _event_records.set_nap_flags(db_session, flags)
    return changes
