"""Tests for flagging the naps already stored for providers that don't report them: the task and its script."""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.classify_sleep_naps_task import (
    MIGRATION,
    classify_sleep_naps,
    classify_sources,
)
from app.integrations.redis_client import get_redis_client
from app.models import DataSource, HealthScore, SleepDetails
from app.repositories.data_migration_repository import DataMigrationRepository
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


_script = _load_module()


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


def _classify(db: Session) -> tuple[UUID | None, int, bool]:
    return classify_sources(db, None, 0, 60)


def _is_nap(db: Session, details: SleepDetails) -> bool | None:
    db.expire_all()
    return db.get(SleepDetails, details.record_id).is_nap


class TestClassifySleepNaps:
    def test_flags_the_naps_of_providers_without_nap_flags(self, db: Session) -> None:
        _, apple_night, apple_nap = _night_and_nap(ProviderName.APPLE)
        _, _, withings_nap = _night_and_nap(ProviderName.WITHINGS)

        assert _classify(db)[1:] == (0, True)
        assert _is_nap(db, apple_nap) is True
        assert _is_nap(db, withings_nap) is True
        assert _is_nap(db, apple_night) is False

    def test_leaves_other_providers_alone(self, db: Session) -> None:
        _, _, garmin_nap = _night_and_nap(ProviderName.GARMIN)

        _classify(db)
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

        _classify(db)

        db.expire_all()
        assert db.query(HealthScore).filter(HealthScore.event_record_id == nap.record_id).count() == 0

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        _night_and_nap(ProviderName.APPLE)

        _classify(db)

        assert _script.count_nap_changes(db) == 0

    def test_a_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        _, _, nap = _night_and_nap(ProviderName.APPLE)

        assert _script.count_nap_changes(db) == 1
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

        with patch.object(event_record_service, "reclassify_sleep_naps", side_effect=flaky):
            assert _classify(db)[1:] == (1, True)

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

        _classify(db)

        db.expire_all()
        assert db.query(HealthScore).filter(HealthScore.event_record_id == late_night.record_id).count() == 1

    def test_a_spent_budget_stops_after_the_source_and_resumes_from_it(self, db: Session) -> None:
        first, _, first_nap = _night_and_nap(ProviderName.APPLE)
        second, _, second_nap = _night_and_nap(ProviderName.APPLE)
        earlier, later = sorted([(first.id, first_nap), (second.id, second_nap)], key=lambda pair: pair[0])

        assert classify_sources(db, None, 0, 0) == (earlier[0], 0, False)
        assert (_is_nap(db, earlier[1]), _is_nap(db, later[1])) == (True, False)

        assert classify_sources(db, earlier[0], 0, 60)[1:] == (0, True)
        assert _is_nap(db, later[1]) is True


def _session(db: Session) -> MagicMock:
    session = MagicMock()
    session.__enter__.return_value = db
    return session


class TestClassifySleepNapsTask:
    def test_records_the_migration_once_every_source_is_done(self, db: Session) -> None:
        _, _, nap = _night_and_nap(ProviderName.APPLE)

        with patch("app.integrations.celery.tasks.classify_sleep_naps_task.SessionLocal", return_value=_session(db)):
            assert classify_sleep_naps() == {"finished": True, "failed": 0}
            assert classify_sleep_naps() == {"skipped": "done"}

        assert _is_nap(db, nap) is True
        assert DataMigrationRepository().is_completed(db, MIGRATION)

    def test_a_failed_source_leaves_the_migration_for_the_next_startup(self, db: Session) -> None:
        _night_and_nap(ProviderName.APPLE)
        db.commit()

        with (
            patch("app.integrations.celery.tasks.classify_sleep_naps_task.SessionLocal", return_value=_session(db)),
            patch.object(event_record_service, "reclassify_sleep_naps", side_effect=RuntimeError("boom")),
        ):
            assert classify_sleep_naps() == {"finished": True, "failed": 1}

        assert not DataMigrationRepository().is_completed(db, MIGRATION)

    def test_an_unfinished_run_queues_the_next_from_its_cursor(self, db: Session) -> None:
        source, _, _ = _night_and_nap(ProviderName.APPLE)

        with (
            patch("app.integrations.celery.tasks.classify_sleep_naps_task.SessionLocal", return_value=_session(db)),
            patch("app.integrations.celery.tasks.classify_sleep_naps_task._BUDGET_SECONDS", 0),
            patch.object(classify_sleep_naps, "apply_async") as apply_async,
        ):
            assert classify_sleep_naps() == {"finished": False, "failed": 0}

        assert apply_async.call_args.kwargs["kwargs"] == {"after": str(source.id), "failed": 0}

    def test_a_run_waits_out_one_already_in_progress(self, db: Session) -> None:
        get_redis_client().set("classify_sleep_naps:lock", "1")

        assert classify_sleep_naps() == {"skipped": "previous_run_in_progress"}


class TestScript:
    def test_queues_the_task_until_it_is_done(self, db: Session) -> None:
        with (
            patch.object(_script, "SessionLocal", return_value=_session(db)),
            patch.object(_script, "create_celery"),
            patch.object(_script.classify_sleep_naps, "delay") as delay,
        ):
            _script.main(dry_run=False)
            DataMigrationRepository().mark_completed(db, MIGRATION)
            _script.main(dry_run=False)

        delay.assert_called_once()


def test_a_run_stops_once_its_lock_is_lost(db: Session) -> None:
    first, _, _ = _night_and_nap(ProviderName.APPLE)
    _night_and_nap(ProviderName.APPLE)
    earliest = min(first.id, *(s.id for s in db.query(DataSource).filter(DataSource.id != first.id)))

    assert classify_sources(db, None, 0, 60, keep_alive=lambda: False) == (earliest, 0, False)
