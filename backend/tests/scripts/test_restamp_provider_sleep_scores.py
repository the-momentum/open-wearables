"""Tests for moving Garmin, Polar and Whoop sleep scores from the night's start to its wake-up."""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EventRecord, HealthScore, User
from app.schemas.enums import HealthScoreCategory, ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, HealthScoreFactory, UserFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "restamp_provider_sleep_scores.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("restamp_provider_sleep_scores", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
restamp_provider_sleep_scores = module.restamp_provider_sleep_scores

START = datetime(2026, 10, 27, 23, 55, tzinfo=timezone.utc)  # 00:55 on the 28th at +01:00
WAKE_UP = datetime(2026, 10, 28, 5, 46, tzinfo=timezone.utc)


def _night(
    user: User, provider: ProviderName, zone_offset: str | None = "+01:00", start: datetime = START
) -> EventRecord:
    source = DataSourceFactory(user=user, provider=provider, source=provider.value)
    return EventRecordFactory(
        data_source=source,
        category="sleep",
        type="sleep_session",
        start_datetime=start,
        end_datetime=WAKE_UP,
        zone_offset=zone_offset,
    )


def _score(
    user: User, provider: ProviderName, recorded_at: datetime, data_source_id: UUID | None = None, **kwargs: object
) -> UUID:
    """The score's id, since the script's commits expire the instance."""
    return HealthScoreFactory(
        user_id=user.id,
        data_source_id=data_source_id,
        provider=provider,
        category=HealthScoreCategory.SLEEP,
        value=Decimal("80"),
        recorded_at=recorded_at,
        **kwargs,
    ).id


def _stamp(db: Session, score_id: UUID) -> tuple[datetime, str | None] | None:
    db.expire_all()
    row = db.get(HealthScore, score_id)
    return (row.recorded_at, row.zone_offset) if row else None


class TestRestampProviderSleepScores:
    def test_moves_garmin_and_whoop_scores_to_the_wake_up(self, db: Session) -> None:
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        _night(user, ProviderName.WHOOP, zone_offset="-05:00")
        garmin = _score(user, ProviderName.GARMIN, START)
        whoop = _score(user, ProviderName.WHOOP, START)

        assert restamp_provider_sleep_scores(db, dry_run=False) == 2
        assert _stamp(db, garmin) == (WAKE_UP, "+01:00")
        assert _stamp(db, whoop) == (WAKE_UP, "-05:00")

    def test_moves_a_polar_score_through_its_event_record(self, db: Session) -> None:
        user = UserFactory()
        night = _night(user, ProviderName.POLAR, zone_offset=None)
        score = _score(user, ProviderName.POLAR, START, event_record_id=night.id)

        assert restamp_provider_sleep_scores(db, dry_run=False) == 1
        assert _stamp(db, score) == (WAKE_UP, None)

    def test_moves_a_polar_score_whose_night_a_re_sync_moved(self, db: Session) -> None:
        """A re-sync replaces a Polar night in place, so its start may no longer be the score's."""
        user = UserFactory()
        night = _night(user, ProviderName.POLAR, zone_offset=None, start=START + timedelta(minutes=10))
        score = _score(user, ProviderName.POLAR, START, event_record_id=night.id)

        assert restamp_provider_sleep_scores(db, dry_run=False) == 1
        assert _stamp(db, score) == (WAKE_UP, None)

    def test_drops_a_score_whose_night_already_has_one_at_the_wake_up(self, db: Session) -> None:
        # Written by the fixed ingestion after the deploy, before this ran
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        old = _score(user, ProviderName.GARMIN, START)
        new = _score(user, ProviderName.GARMIN, WAKE_UP, zone_offset="+01:00")

        restamp_provider_sleep_scores(db, dry_run=False)

        assert _stamp(db, old) is None
        assert _stamp(db, new) == (WAKE_UP, "+01:00")

    def test_keeps_the_newest_of_two_scores_moving_to_one_wake_up(self, db: Session) -> None:
        """Two copies of a night that differ in their start send both scores to one wake-up."""
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        _night(user, ProviderName.GARMIN, start=START + timedelta(minutes=10))
        older = _score(user, ProviderName.GARMIN, START, created_at=START)
        newer = _score(user, ProviderName.GARMIN, START + timedelta(minutes=10), created_at=WAKE_UP)

        assert restamp_provider_sleep_scores(db, dry_run=False) == 1
        assert _stamp(db, older) is None
        assert _stamp(db, newer) == (WAKE_UP, "+01:00")

    def test_a_score_of_another_source_at_the_wake_up_does_not_block_the_move(self, db: Session) -> None:
        """The unique key includes the source (#1877), so that time is still free for the score."""
        user = UserFactory()
        night = _night(user, ProviderName.GARMIN)
        moving = _score(user, ProviderName.GARMIN, START)
        other = _score(user, ProviderName.GARMIN, WAKE_UP, data_source_id=night.data_source_id)

        restamp_provider_sleep_scores(db, dry_run=False)

        assert _stamp(db, moving) == (WAKE_UP, "+01:00")
        assert _stamp(db, other) is not None

    def test_leaves_other_scores_alone(self, db: Session) -> None:
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        _night(user, ProviderName.OURA)
        oura = _score(user, ProviderName.OURA, START)
        internal = _score(user, ProviderName.INTERNAL, START)
        without_night = _score(user, ProviderName.GARMIN, START - timedelta(days=1))

        assert restamp_provider_sleep_scores(db, dry_run=False) == 0
        assert _stamp(db, oura) == (START, None)
        assert _stamp(db, internal) == (START, None)
        assert _stamp(db, without_night) == (START - timedelta(days=1), None)

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        score = _score(user, ProviderName.GARMIN, START)

        restamp_provider_sleep_scores(db, dry_run=False)

        assert restamp_provider_sleep_scores(db, dry_run=False) == 0
        assert _stamp(db, score) == (WAKE_UP, "+01:00")

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        user = UserFactory()
        _night(user, ProviderName.GARMIN)
        score = _score(user, ProviderName.GARMIN, START)

        assert restamp_provider_sleep_scores(db, dry_run=True) == 1
        assert _stamp(db, score) == (START, None)
