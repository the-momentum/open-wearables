"""Whether a sleep session is final: from its provider and state, else from the provider's data after it."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from app.services.sleep_finality import final_record_ids, finality_from_state
from tests.factories import DataPointSeriesFactory, DataSourceFactory, EventRecordFactory, SleepDetailsFactory

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
        ("google_health", None, 100, None),
        ("oura", None, 100, None),
        ("suunto", None, 100, None),
    ],
)
def test_finality_from_state(provider: str, state: str | None, hours_since_end: float, final: bool | None) -> None:
    end = NOW - timedelta(hours=hours_since_end)

    assert finality_from_state(provider, state, end, NOW) is final


def test_final_record_ids_decides_by_state_then_by_data(db: Session) -> None:
    end = NOW - timedelta(days=2)
    sessions = []
    for provider, state in (
        (ProviderName.OURA, None),
        (ProviderName.OURA, None),
        (ProviderName.GARMIN, "ENHANCED_FINAL"),
        (ProviderName.WHOOP, "PENDING_SCORE"),
    ):
        source = DataSourceFactory(provider=provider)
        record = EventRecordFactory(
            mapping=source,
            category="sleep",
            type_="sleep",
            start_datetime=end - timedelta(hours=8),
            end_datetime=end,
        )
        SleepDetailsFactory(event_record=record, provider_state=state)
        sessions.append((record, source))
    with_data, without_data, garmin, whoop = sessions
    for _, source in (with_data, whoop):
        DataPointSeriesFactory(data_source=source, recorded_at=end + timedelta(minutes=30))
    db.expire_all()

    found = final_record_ids(db, sessions, NOW)

    assert found == {with_data[0].id, garmin[0].id}
