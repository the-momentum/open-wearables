"""Whether a sleep session is final: from its provider and state, else from the provider's latest data."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, User
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.enums import ProviderName
from app.schemas.sync_status import DataTypeKind
from app.services.sleep_finality import final_record_ids, finality_from_state
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("provider", "state", "hours_since_end", "final"),
    [
        ("apple", None, 0, True),
        ("samsung", None, 0, True),
        ("health_connect", None, 0, True),
        ("garmin", "ENHANCED_FINAL", 0, True),
        ("garmin", "MANUAL", 0, True),
        ("garmin", "AUTO_TENTATIVE", 11.99, False),
        ("garmin", "AUTO_TENTATIVE", 12, True),
        ("garmin", None, 11.99, False),
        ("garmin", None, 12, True),
        ("whoop", "PENDING_SCORE", 100, False),
        ("whoop", "UNSCORABLE", 0, True),
        ("whoop", "SCORED", 5.99, False),
        ("whoop", "SCORED", 6, True),
        ("whoop", None, 6, True),
        ("google_health", "processed", 0, True),
        ("google_health", "processing", 23.99, False),
        ("google_health", "processing", 24, True),
        ("google_health", None, 23.99, False),
        ("google_health", None, 24, True),
        ("oura", None, 100, None),
        ("suunto", None, 100, None),
    ],
)
def test_finality_from_state(provider: str, state: str | None, hours_since_end: float, final: bool | None) -> None:
    end = NOW - timedelta(hours=hours_since_end)

    assert finality_from_state(provider, state, end, NOW) is final


def _night(user: User, provider: ProviderName, end: datetime, state: str | None) -> tuple[EventRecord, DataSource]:
    source = DataSourceFactory(user=user, provider=provider)
    record = EventRecordFactory(
        mapping=source, category="sleep", type_="sleep", start_datetime=end - timedelta(hours=8), end_datetime=end
    )
    SleepDetailsFactory(event_record=record, provider_state=state)
    return record, source


def test_final_record_ids_decides_by_state_then_by_the_providers_latest_data(db: Session) -> None:
    user = UserFactory()
    latest_data = NOW - timedelta(hours=1)
    data_type_coverage_repository.record(
        db,
        [
            CoverageSpan(user.id, provider, "heart_rate", DataTypeKind.SERIES, NOW - timedelta(days=30), latest_data)
            for provider in ("oura", "whoop")
        ],
    )
    nights = {
        name: _night(user, provider, end, state)
        for name, provider, end, state in (
            ("oura_synced_since", ProviderName.OURA, latest_data - timedelta(days=1), None),
            ("oura_not_yet", ProviderName.OURA, latest_data - timedelta(minutes=29), None),
            ("suunto", ProviderName.SUUNTO, NOW - timedelta(days=2), None),
            ("garmin", ProviderName.GARMIN, NOW - timedelta(hours=1), "ENHANCED_FINAL"),
            ("whoop", ProviderName.WHOOP, NOW - timedelta(days=2), "PENDING_SCORE"),
        )
    }
    db.expire_all()

    found = final_record_ids(db, user.id, list(nights.values()), NOW)

    assert found == {nights["oura_synced_since"][0].id, nights["garmin"][0].id}


def test_a_later_night_counts_as_the_providers_latest_data(db: Session) -> None:
    """A Withings Sleep Analyzer sends nights and nothing else: a night is final once the next one arrives."""
    user = UserFactory()
    last_end = NOW - timedelta(hours=3)
    earlier, last = (_night(user, ProviderName.WITHINGS, last_end - timedelta(days=days), None) for days in (1, 0))
    data_type_coverage_repository.record(
        db, [CoverageSpan(user.id, "withings", "sleep", DataTypeKind.EVENT, last_end - timedelta(days=2), last_end)]
    )
    db.expire_all()

    assert final_record_ids(db, user.id, [earlier, last], NOW) == {earlier[0].id}
