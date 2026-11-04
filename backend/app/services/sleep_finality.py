"""Whether a sleep session is the night's final data: no more of it is expected from the provider."""

from datetime import datetime, timedelta
from uuid import UUID

from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories.sleep_finality_repository import sleep_finality_repository
from app.schemas.enums import ProviderName

# A source that sent data from this long after a session's end synced after the session was over, not at its end.
# On one instance's Oura data (51 nights, 2026-11) 30 minutes let 2 of 42 partial nights through and passed a full
# night a median 70 minutes after waking.
DATA_AFTER_END = timedelta(minutes=30)
# Garmin's *_TENTATIVE nights end at a real awakening, so data after them proves nothing, and a user with several
# devices never gets *_FINAL.
GARMIN_TENTATIVE_FINAL_AFTER = timedelta(hours=12)
# Whoop extended SCORED nights up to 4.5 hours after their end (6 of 294 nights, 2026-11).
WHOOP_SCORED_FINAL_AFTER = timedelta(hours=6)
# Google Health: processed=false means the sleep is detected but its stages are still processing; a night whose
# processing never finishes doesn't stay non-final.
GOOGLE_PROCESSING_FINAL_AFTER = timedelta(hours=24)


def finality_from_state(provider: str, provider_state: str | None, end: datetime, now: datetime) -> bool | None:
    """Whether a session is final from its provider and state alone; None when the source's data decides."""
    if provider in SDK_PROVIDERS:
        return True  # the SDK writes a session only once it is over
    if provider == ProviderName.GARMIN:
        if provider_state and not provider_state.endswith("_TENTATIVE"):
            return True
        return now >= end + GARMIN_TENTATIVE_FINAL_AFTER
    if provider == ProviderName.WHOOP:
        if provider_state == "PENDING_SCORE":
            return False
        if provider_state == "UNSCORABLE":
            return True  # it won't change
        return now >= end + WHOOP_SCORED_FINAL_AFTER
    if provider == ProviderName.GOOGLE_HEALTH and provider_state is not None:
        return provider_state == "processed" or now >= end + GOOGLE_PROCESSING_FINAL_AFTER
    return None


def final_record_ids(db_session: DbSession, sessions: list[tuple[EventRecord, DataSource]], now: datetime) -> set[UUID]:
    """The ids of the final sessions: by provider and state, else by the source's data after the session's end."""
    final: set[UUID] = set()
    by_data: list[tuple[UUID, UUID, datetime]] = []
    for record, data_source in sessions:
        state = record.sleep_detail.provider_state if record.sleep_detail else None
        decided = finality_from_state(data_source.provider, state, record.end_datetime, now)
        if decided is None:
            by_data.append((record.id, data_source.id, record.end_datetime + DATA_AFTER_END))
        elif decided:
            final.add(record.id)
    return final | sleep_finality_repository.with_data_since(db_session, by_data)
