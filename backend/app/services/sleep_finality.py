"""Whether a sleep session is the night's final data: no more of it is expected from the provider."""

from datetime import datetime, timedelta
from uuid import UUID

from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import DbSession
from app.models import DataSource, EventRecord
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.enums import ProviderName, SeriesType
from app.schemas.sync_status import DataTypeKind

# A night counts as final once its provider has sent data from this long after its end: a partial night ends at the
# sync that sent it.
_DATA_AFTER_END = timedelta(minutes=30)
# A Garmin *_TENTATIVE night counts as final this long after its end: users with several devices never get *_FINAL.
_GARMIN_TENTATIVE_FINAL_AFTER = timedelta(hours=12)
# A scored Whoop night counts as final this long after its end: Whoop can still extend it for a few hours.
_WHOOP_SCORED_FINAL_AFTER = timedelta(hours=6)
# A Google Health night still processing counts as final this long after its end, in case processing never finishes.
_GOOGLE_PROCESSING_FINAL_AFTER = timedelta(hours=24)
# Series a device sends with every sync, so their latest data tells when the provider last synced.
_SYNC_SERIES = (SeriesType.steps.value, SeriesType.heart_rate.value, SeriesType.physical_effort.value)


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
    if provider == ProviderName.GOOGLE_HEALTH and provider_state is not None:
        return provider_state == "processed" or now >= end + _GOOGLE_PROCESSING_FINAL_AFTER
    return None


def final_record_ids(
    db_session: DbSession, user_id: UUID, sessions: list[tuple[EventRecord, DataSource]], now: datetime
) -> set[UUID]:
    """The ids of the user's final sessions: by provider and state, else by the provider's latest data."""
    latest_data = _latest_data_by_provider(db_session, user_id)
    final: set[UUID] = set()
    for record, data_source in sessions:
        state = record.sleep_detail.provider_state if record.sleep_detail else None
        decided = finality_from_state(data_source.provider, state, record.end_datetime, now)
        if decided is None:
            latest = latest_data.get(data_source.provider)
            decided = latest is not None and latest >= record.end_datetime + _DATA_AFTER_END
        if decided:
            final.add(record.id)
    return final


def _latest_data_by_provider(db_session: DbSession, user_id: UUID) -> dict[str, datetime]:
    """When each of the user's providers last sent steps, heart rate or MET data."""
    latest: dict[str, datetime] = {}
    for held in data_type_coverage_repository.list_for_user(db_session, user_id, data_types=_SYNC_SERIES):
        if held.kind == DataTypeKind.SERIES:
            latest[held.provider] = max(latest.get(held.provider, held.coverage_end), held.coverage_end)
    return latest
