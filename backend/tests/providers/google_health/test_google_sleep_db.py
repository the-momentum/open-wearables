"""Google Health sleep sync against a real database, through ``load_and_save_all``."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EventRecord
from app.schemas.enums import DataGranularity, EventCategory, ProviderName
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.helpers import GOOGLE_HEALTH_API_SOURCE
from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory

END = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
START = END - timedelta(days=7)
BEDTIME = START + timedelta(hours=8)


def _name(name: str) -> str:
    return f"users/me/dataTypes/sleep/dataPoints/{name}"


def _session(name: str, start: datetime, hours: float = 7) -> dict:
    minutes = int(hours * 60)
    return {
        "name": _name(name),
        "dataSource": {"platform": "FITBIT", "device": {"displayName": "Fitbit Air"}},
        "sleep": {
            "interval": {
                "startTime": start.isoformat(),
                "endTime": (start + timedelta(hours=hours)).isoformat(),
                "startUtcOffset": "19800s",
            },
            "summary": {"minutesInSleepPeriod": minutes, "minutesAsleep": minutes - 20},
        },
    }


def _sync(db: Session, user_id: UUID, points: list[dict]) -> None:
    data_247 = GoogleHealth247Data(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="https://x")
    module = "app.services.providers.google_health.data_247"
    with (
        patch(f"{module}.METRICS", ()),
        patch(f"{module}.DERIVED_DAILY_METRICS", ()),
        patch(f"{module}.DAILY_ROLLUP_METRICS", ()),
        patch.object(data_247.nutrition, "load_and_save", return_value=0),
        patch.object(data_247.settings_repo, "get_data_granularity", return_value=DataGranularity.RAW),
        patch(
            "app.services.providers.google_health.sleep.make_authenticated_request",
            return_value={"dataPoints": points},
        ),
        patch("app.services.providers.google_health.sleep.store_raw_payload"),
    ):
        result = data_247.load_and_save_all(db, user_id, START, END)
    assert "sleep" not in result.failures


def _stored(db: Session) -> list[tuple[str, int | None]]:
    """(data point name, minutes in bed) of each stored session, oldest first."""
    db.expire_all()
    records = (
        db.query(EventRecord)
        .filter(EventRecord.category == EventCategory.SLEEP)
        .order_by(EventRecord.start_datetime)
        .all()
    )
    return [
        ((r.external_id or "").rsplit("/", 1)[-1], r.sleep_detail and r.sleep_detail.sleep_time_in_bed_minutes)
        for r in records
    ]


def test_every_session_in_the_window_is_stored(db: Session) -> None:
    # The sleep step used to run in a savepoint that the first per-session commit closed.
    user = UserFactory()
    db.commit()

    _sync(db, user.id, [_session(f"n{i}", BEDTIME + timedelta(days=i)) for i in range(3)])

    assert _stored(db) == [("n0", 420), ("n1", 420), ("n2", 420)]


def test_a_revised_session_replaces_the_stored_one(db: Session) -> None:
    user = UserFactory()
    db.commit()

    _sync(db, user.id, [_session("n0", BEDTIME, hours=6)])
    _sync(db, user.id, [_session("n0", BEDTIME, hours=7)])

    assert _stored(db) == [("n0", 420)]


def test_copies_under_other_data_sources_collapse_to_one(db: Session) -> None:
    # What a device rename left behind before sessions were keyed on their name.
    user = UserFactory()
    for device in ("Google Fitbit Air", "Fitbit Air"):
        source = DataSourceFactory(
            user=user, provider=ProviderName.GOOGLE_HEALTH, source=GOOGLE_HEALTH_API_SOURCE, device_model=device
        )
        EventRecordFactory(
            data_source=source,
            category=EventCategory.SLEEP,
            type=None,
            external_id=_name("n0"),
            start_datetime=BEDTIME,
            end_datetime=BEDTIME + timedelta(hours=7),
        )
    db.commit()

    _sync(db, user.id, [_session("n0", BEDTIME)])

    assert _stored(db) == [("n0", 420)]
    assert db.query(EventRecord.type).scalar() == "sleep_session"


def test_a_session_reissued_under_a_new_name_takes_the_new_name(db: Session) -> None:
    user = UserFactory()
    source = DataSourceFactory(
        user=user, provider=ProviderName.GOOGLE_HEALTH, source=GOOGLE_HEALTH_API_SOURCE, device_model="Fitbit Air"
    )
    EventRecordFactory(
        data_source=source,
        category=EventCategory.SLEEP,
        external_id=_name("old"),
        start_datetime=BEDTIME,
        end_datetime=BEDTIME + timedelta(hours=7),
    )
    db.commit()

    _sync(db, user.id, [_session("new", BEDTIME)])

    assert _stored(db) == [("new", 420)]


def test_a_nap_next_to_a_night_survives_a_resync(db: Session) -> None:
    # Within sleep_end_gap_minutes: create_or_merge_sleep would merge them, then shrink the
    # merged record to one of them when the next sync fetched both again.
    user = UserFactory()
    db.commit()
    points = [_session("night", BEDTIME, hours=6), _session("nap", BEDTIME - timedelta(hours=2), hours=1)]

    _sync(db, user.id, points)
    _sync(db, user.id, points)

    assert _stored(db) == [("nap", 60), ("night", 360)]
