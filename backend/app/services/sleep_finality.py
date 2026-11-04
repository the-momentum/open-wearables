"""Whether a sleep session is the night's final data: no more of it is expected from the provider."""

from datetime import datetime, timedelta
from uuid import UUID

from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.enums import EventCategory, ProviderName, SeriesType
from app.schemas.sync_status import DataTypeKind

# A night counts as final once its provider has sent data from this long after its end: a partial night ends at the
# sync that sent it.
_DATA_AFTER_END = timedelta(minutes=30)
# A Garmin *_TENTATIVE night counts as final this long after its end: users with several devices never get *_FINAL.
_GARMIN_TENTATIVE_FINAL_AFTER = timedelta(hours=12)
# A scored Whoop night counts as final this long after its end: Whoop can still extend it for a few hours.
_WHOOP_SCORED_FINAL_AFTER = timedelta(hours=6)
# A Google Health night not marked processed counts as final this long after its end, in case it never is.
_GOOGLE_PROCESSING_FINAL_AFTER = timedelta(hours=24)
# Data whose latest record tells when the provider last synced: series a device sends with every sync, and the
# nights and workouts themselves, as some devices (a Withings Sleep Analyzer) send nothing else.
_SYNC_DATA = {
    (DataTypeKind.SERIES, SeriesType.steps.value),
    (DataTypeKind.SERIES, SeriesType.heart_rate.value),
    (DataTypeKind.SERIES, SeriesType.physical_effort.value),
    (DataTypeKind.EVENT, EventCategory.SLEEP.value),
    (DataTypeKind.EVENT, EventCategory.WORKOUT.value),
}


def finality_from_state(provider: str, provider_state: str | None, end: datetime, now: datetime) -> bool | None:
    """Whether a session is final from its provider and state alone; None when the provider's data decides."""
    if provider in SDK_PROVIDERS:
        return True  # the SDK path writes a session once its end gap or upload quiet has passed
    if provider == ProviderName.GARMIN:
        if provider_state and not provider_state.endswith("_TENTATIVE"):
            return True
        return now >= end + _GARMIN_TENTATIVE_FINAL_AFTER
    if provider == ProviderName.WHOOP:
        if provider_state == "PENDING_SCORE":
            return False
        if provider_state == "UNSCORABLE":
            return True  # it won't change
        return now >= end + _WHOOP_SCORED_FINAL_AFTER
    if provider == ProviderName.GOOGLE_HEALTH:
        return provider_state == "processed" or now >= end + _GOOGLE_PROCESSING_FINAL_AFTER
    return None


def final_record_ids(
    db_session: DbSession, user_id: UUID, sessions: list[tuple[EventRecord, DataSource]], now: datetime
) -> set[UUID]:
    """The ids of the user's final sessions: by provider and state, else by the provider's latest data."""
    final: set[UUID] = set()
    by_data: list[tuple[EventRecord, str]] = []
    for record, data_source in sessions:
        state = record.sleep_detail.provider_state if record.sleep_detail else None
        decided = finality_from_state(data_source.provider, state, record.end_datetime, now)
        if decided is None:
            by_data.append((record, data_source.provider))
        elif decided:
            final.add(record.id)
    if not by_data:
        return final
    latest_data = _latest_data_by_provider(db_session, user_id)
    for record, provider in by_data:
        latest = latest_data.get(provider)
        if latest is not None and latest >= record.end_datetime + _DATA_AFTER_END:
            final.add(record.id)
    return final


def _latest_data_by_provider(db_session: DbSession, user_id: UUID) -> dict[str, datetime]:
    """When each of the user's providers last sent data of `_SYNC_DATA`."""
    latest: dict[str, datetime] = {}
    data_types = {data_type for _, data_type in _SYNC_DATA}
    for held in data_type_coverage_repository.list_for_user(db_session, user_id, data_types=data_types):
        if (held.kind, held.data_type) in _SYNC_DATA:
            latest[held.provider] = max(latest.get(held.provider, held.coverage_end), held.coverage_end)
    return latest
