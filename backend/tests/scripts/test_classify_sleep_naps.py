"""Tests for flagging the naps already stored for providers that don't report them."""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, HealthScore, SleepDetails
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.services.event_record_service import event_record_service
from tests.factories import DataSourceFactory, EventRecordFactory, HealthScoreFactory, SleepDetailsFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "classify_sleep_naps.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("classify_sleep_naps", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classify_sleep_naps = _load_module().classify_sleep_naps


def _stored(source: DataSource, start: datetime, end: datetime, asleep_minutes: int) -> SleepDetails:
    record = EventRecordFactory(
        data_source=source,
        category="sleep",
        type="sleep_session",
        start_datetime=start,
        end_datetime=end,
        duration_seconds=int((end - start).total_seconds()),
        zone_offset="+00:00",
    )
    return SleepDetailsFactory(event_record=record, sleep_total_duration_minutes=asleep_minutes, is_nap=False)


def _night_and_nap(provider: ProviderName) -> tuple[DataSource, SleepDetails, SleepDetails]:
    source = DataSourceFactory(provider=provider, source=provider.value)
    night = _stored(
        source, datetime(2025, 3, 22, 23, tzinfo=timezone.utc), datetime(2025, 3, 23, 7, tzinfo=timezone.utc), 450
    )
    nap = _stored(
        source, datetime(2025, 3, 23, 13, tzinfo=timezone.utc), datetime(2025, 3, 23, 14, 30, tzinfo=timezone.utc), 80
    )
    return source, night, nap


def _is_nap(db: Session, details: SleepDetails) -> bool | None:
    db.expire_all()
    return db.get(SleepDetails, details.record_id).is_nap


class TestClassifySleepNaps:
    def test_flags_the_naps_of_providers_without_nap_flags(self, db: Session) -> None:
        _, apple_night, apple_nap = _night_and_nap(ProviderName.APPLE)
        _, _, withings_nap = _night_and_nap(ProviderName.WITHINGS)

        assert classify_sleep_naps(db, dry_run=False) == 2
        assert _is_nap(db, apple_nap) is True
        assert _is_nap(db, withings_nap) is True
        assert _is_nap(db, apple_night) is False

    def test_leaves_other_providers_alone(self, db: Session) -> None:
        _, _, garmin_nap = _night_and_nap(ProviderName.GARMIN)

        assert classify_sleep_naps(db, dry_run=False) == 0
        assert _is_nap(db, garmin_nap) is False

    def test_removes_the_internal_sleep_score_of_a_nap(self, db: Session) -> None:
        source, _, nap = _night_and_nap(ProviderName.APPLE)
        # Scored as main sleep before the migration, as fill_missing_sleep_scores did
        HealthScoreFactory(
            user_id=source.user_id,
            data_source_id=source.id,
            provider=ProviderName.INTERNAL,
            category=HealthScoreCategory.SLEEP,
            recorded_at=datetime(2025, 3, 23, 14, 30, tzinfo=timezone.utc),
            event_record_id=nap.record_id,
        )

        classify_sleep_naps(db, dry_run=False)

        db.expire_all()
        assert db.query(HealthScore).filter(HealthScore.event_record_id == nap.record_id).count() == 0

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        _night_and_nap(ProviderName.APPLE)

        classify_sleep_naps(db, dry_run=False)

        assert classify_sleep_naps(db, dry_run=False) == 0

    def test_a_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        _, _, nap = _night_and_nap(ProviderName.APPLE)

        assert classify_sleep_naps(db, dry_run=True) == 1
        assert _is_nap(db, nap) is False

    def test_a_failing_source_does_not_stop_the_others(self, db: Session) -> None:
        failing_source, _, failing_nap = _night_and_nap(ProviderName.APPLE)
        _, _, other_nap = _night_and_nap(ProviderName.APPLE)
        failing_id = failing_source.id
        db.commit()  # the failing source's rollback must not take the fixtures with it
        original = event_record_service.reclassify_sleep_naps

        def flaky(session: Session, user_id: UUID, source_id: UUID, wake_dates: set[date] | None) -> int:
            if source_id == failing_id:
                raise RuntimeError("boom")
            return original(session, user_id, source_id, wake_dates)

        with (
            patch.object(event_record_service, "reclassify_sleep_naps", side_effect=flaky),
            pytest.raises(RuntimeError),
        ):
            classify_sleep_naps(db, dry_run=False)

        assert _is_nap(db, other_nap) is True
        assert _is_nap(db, failing_nap) is False

    def test_keeps_the_scores_of_nap_days_months_apart(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.APPLE, source="apple")
        first_night = datetime(2025, 1, 1, 23, tzinfo=timezone.utc)
        nights = [
            _stored(source, first_night + timedelta(days=i), first_night + timedelta(days=i, hours=8), 450)
            for i in range(150)
        ]
        _stored(
            source, datetime(2025, 1, 2, 13, tzinfo=timezone.utc), datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc), 80
        )
        _stored(
            source,
            datetime(2025, 5, 28, 13, tzinfo=timezone.utc),
            datetime(2025, 5, 28, 14, 30, tzinfo=timezone.utc),
            80,
        )
        late_night = nights[(date(2025, 5, 27) - date(2025, 1, 1)).days]  # ends on 2025-05-28
        # Scored before the migration, as fill_missing_sleep_scores did
        HealthScoreFactory(
            user_id=source.user_id,
            data_source_id=source.id,
            provider=ProviderName.INTERNAL,
            category=HealthScoreCategory.SLEEP,
            recorded_at=datetime(2025, 5, 28, 7, tzinfo=timezone.utc),
            event_record_id=late_night.record_id,
        )
        db.flush()

        assert classify_sleep_naps(db, dry_run=False) == 2

        db.expire_all()
        assert db.query(HealthScore).filter(HealthScore.event_record_id == late_night.record_id).count() == 1
