"""Tests for the correction of Polar workout times, see scripts/data_migrations/fix_polar_workout_utc_offset.py."""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.integrations.rollup_queue import pop_dirty_days
from app.models import EventRecord
from app.schemas.auth import ConnectionStatus
from app.schemas.enums.provider import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, UserConnectionFactory, UserFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "fix_polar_workout_utc_offset.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fix_polar_workout_utc_offset", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()
fix = _module.fix_polar_workout_times
migrate = _module._migrate

# Polar says 09:20 local at +2, so the truth is 07:20 UTC. The old code stored 11:20.
_LOCAL = "2026-09-12T09:20:47"
_OFFSET = 120
_DURATION = timedelta(seconds=4412)
_STALE_START = datetime(2026, 9, 12, 11, 20, 47, tzinfo=timezone.utc)
_TRUE_START = datetime(2026, 9, 12, 7, 20, 47, tzinfo=timezone.utc)


def _workouts_api(exercises: dict[str, dict], refused: dict[UUID, Exception] | None = None) -> MagicMock:
    """A PolarWorkouts stand-in: real offset maths, Polar's exercise list as canned JSON by exercise id."""
    from app.services.providers.polar.workouts import PolarWorkouts

    api = MagicMock()
    api._extract_dates_with_offset = PolarWorkouts._extract_dates_with_offset.__get__(api)

    def exercise_list(_db: Session, user_id: UUID, **_kwargs: Any) -> list[dict]:
        if refused and user_id in refused:
            raise refused[user_id]
        return [{**exercise, "id": exercise_id} for exercise_id, exercise in exercises.items()]

    api.get_workouts_from_api.side_effect = exercise_list
    return api


def _polar_json() -> dict:
    return {"start_time": _LOCAL, "start_time_utc_offset": _OFFSET, "duration": "PT4412S"}


def _stale_workout(
    db: Session,
    external_id: str,
    *,
    active: bool = True,
    zone_offset: str | None = "+02:00",
    start: datetime = _STALE_START,
    duration: timedelta = _DURATION,
    source: Any = None,
) -> tuple[EventRecord, Any]:
    if source is None:
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE if active else ConnectionStatus.REVOKED,
        )
        source = DataSourceFactory(user=user, provider=ProviderName.POLAR, source="polar")
    record = EventRecordFactory(
        data_source=source,
        external_id=external_id,
        start_datetime=start,
        end_datetime=start + duration,
        zone_offset=zone_offset,
    )
    return record, source


def _start_of(db: Session, record_id: UUID) -> datetime | None:
    row = db.get(EventRecord, record_id)
    return row.start_datetime if row else None


class TestCorrection:
    def test_moves_the_row_to_its_true_utc_time(self, db: Session) -> None:
        # Arrange
        record, _ = _stale_workout(db, "EX1")

        # Act
        counts = fix(db, _workouts_api({"EX1": _polar_json()}), dry_run=False)

        # Assert
        db.expire_all()
        assert _start_of(db, record.id) == _TRUE_START
        assert counts["corrected"] == 1

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        # Arrange
        record, _ = _stale_workout(db, "EX1")

        # Act
        fix(db, _workouts_api({"EX1": _polar_json()}), dry_run=True)

        # Assert
        db.expire_all()
        assert _start_of(db, record.id) == _STALE_START

    def test_is_idempotent(self, db: Session) -> None:
        # Arrange
        record, _ = _stale_workout(db, "EX1")
        api = _workouts_api({"EX1": _polar_json()})

        # Act
        fix(db, api, dry_run=False)
        db.expire_all()
        second = fix(db, api, dry_run=False)

        # Assert
        assert second["corrected"] == 0
        assert second["already_correct"] == 1


class TestAlreadySyncedCopy:
    """A sync on the fixed code ran before the script: the corrected copy exists."""

    def test_drops_the_stale_row_instead_of_colliding(self, db: Session) -> None:
        # Arrange
        stale, source = _stale_workout(db, "EX1")
        copy = EventRecordFactory(
            data_source=source,
            external_id="EX1",
            start_datetime=_TRUE_START,
            end_datetime=_TRUE_START + _DURATION,
        )
        stale_id, copy_id = stale.id, copy.id

        # Act — moving the stale row onto the copy's key would raise a unique violation
        counts = fix(db, _workouts_api({"EX1": _polar_json()}), dry_run=False)

        # Assert
        db.expire_all()
        assert db.get(EventRecord, stale_id) is None
        assert _start_of(db, copy_id) == _TRUE_START
        assert counts["duplicate_dropped"] == 1

    def test_never_deletes_a_different_workout_in_the_way(self, db: Session) -> None:
        # Arrange
        stale, source = _stale_workout(db, "EX1")
        other = EventRecordFactory(
            data_source=source,
            external_id="SOMETHING_ELSE",
            start_datetime=_TRUE_START,
            end_datetime=_TRUE_START + _DURATION,
        )

        # Act — the other workout is Polar too, and already at its true time
        counts = fix(db, _workouts_api({"EX1": _polar_json(), "SOMETHING_ELSE": _polar_json()}), dry_run=False)

        # Assert — both survive untouched
        db.expire_all()
        assert _start_of(db, stale.id) == _STALE_START
        assert _start_of(db, other.id) == _TRUE_START
        assert counts["blocked"] == 1


class TestFailures:
    def test_a_workout_no_longer_on_polars_list_moves_by_its_stored_offset(self, db: Session) -> None:
        """The sync reads the same list, so the fixed code can't have written it."""
        # Arrange
        listed, source = _stale_workout(db, "EX1")
        gone, _ = _stale_workout(db, "GONE", source=source, start=_STALE_START + timedelta(days=1))

        # Act
        counts = fix(db, _workouts_api({"EX1": _polar_json()}), dry_run=False)

        # Assert
        db.expire_all()
        assert _start_of(db, listed.id) == _TRUE_START
        assert _start_of(db, gone.id) == _TRUE_START + timedelta(days=1)
        assert (counts["corrected"], counts["corrected_from_offset"]) == (1, 1)

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_a_token_polar_refuses_moves_its_workouts_by_the_stored_offset(self, db: Session, status_code: int) -> None:
        # Arrange
        refused, refused_source = _stale_workout(db, "GONE")
        fetched, _ = _stale_workout(db, "EX1")
        api = _workouts_api({"EX1": _polar_json()}, {refused_source.user_id: HTTPException(status_code=status_code)})

        # Act
        counts = fix(db, api, dry_run=False)

        # Assert
        db.expire_all()
        assert _start_of(db, refused.id) == _TRUE_START
        assert _start_of(db, fetched.id) == _TRUE_START
        assert (counts["corrected"], counts["corrected_from_offset"]) == (1, 1)

    def test_any_other_failure_aborts(self, db: Session) -> None:
        """Skipping a row the next sync CAN fetch would leave it to be duplicated."""
        # Arrange
        _, source = _stale_workout(db, "FLAKY")
        api = _workouts_api({}, {source.user_id: HTTPException(status_code=502)})

        # Act / Assert
        with pytest.raises(HTTPException):
            fix(db, api, dry_run=False)

    def test_a_user_without_an_active_connection_moves_by_the_stored_offset_without_a_call(self, db: Session) -> None:
        # Arrange
        record, _ = _stale_workout(db, "EX1", active=False)
        api = _workouts_api({})

        # Act
        counts = fix(db, api, dry_run=False)

        # Assert
        api.get_workouts_from_api.assert_not_called()
        db.expire_all()
        assert _start_of(db, record.id) == _TRUE_START
        assert counts["corrected_from_offset"] == 1

    def test_a_workout_without_a_stored_offset_is_left_alone(self, db: Session) -> None:
        """Stored before zone_offset was (#608): there is nothing to move it by."""
        # Arrange
        record, _ = _stale_workout(db, "EX1", active=False, zone_offset=None)

        # Act
        counts = fix(db, _workouts_api({}), dry_run=False)

        # Assert
        db.expire_all()
        assert _start_of(db, record.id) == _STALE_START
        assert counts["no_offset"] == 1


class TestPolarCalls:
    def test_reads_each_users_exercise_list_once(self, db: Session) -> None:
        """Polar's rate limit is shared by the whole instance: one call per user, not per workout."""
        # Arrange
        _, source = _stale_workout(db, "EX1")
        _stale_workout(db, "EX2", source=source, start=_STALE_START + timedelta(days=1))
        api = _workouts_api({"EX1": _polar_json()})

        # Act
        fix(db, api, dry_run=False)

        # Assert
        assert api.get_workouts_from_api.call_count == 1

    def test_reads_polar_before_writing_anything(self, db: Session) -> None:
        """A token refresh commits the session, so a write before a later failing call would stick."""
        # Arrange: the first user's workout comes first in the run, the second user's call fails
        first, first_source = _stale_workout(db, "EX1", start=_STALE_START + timedelta(days=1))
        _, second_source = _stale_workout(db, "EX2")
        api = _workouts_api({}, {second_source.user_id: HTTPException(status_code=502)})
        listed = api.get_workouts_from_api.side_effect

        def refreshing(db_session: Session, user_id: UUID, **kwargs: Any) -> list[dict]:
            db_session.commit()
            return listed(db_session, user_id, **kwargs)

        api.get_workouts_from_api.side_effect = refreshing

        # Act
        with pytest.raises(HTTPException):
            fix(db, api, dry_run=False)

        # Assert
        db.rollback()
        db.expire_all()
        assert _start_of(db, first.id) == _STALE_START + timedelta(days=1)

    def test_an_exercise_missing_its_offset_moves_by_the_stored_one(self, db: Session) -> None:
        # Arrange
        record, _ = _stale_workout(db, "EX1")
        incomplete = {"start_time": _LOCAL, "duration": "PT4412S"}

        # Act
        counts = fix(db, _workouts_api({"EX1": incomplete}), dry_run=False)

        # Assert
        db.expire_all()
        assert _start_of(db, record.id) == _TRUE_START
        assert counts["corrected_from_offset"] == 1


class TestRollupAndCoverage:
    def test_queues_the_old_and_new_local_days_for_the_rollup(self, db: Session) -> None:
        # Arrange: 23:00 local at +2 on 12 September; the old code stored 01:00 UTC on the 13th.
        pop_dirty_days(100)
        record, source = _stale_workout(
            db, "EX1", start=datetime(2026, 9, 13, 1, 0, tzinfo=timezone.utc), duration=timedelta(minutes=30)
        )
        late = {"start_time": "2026-09-12T23:00:00", "start_time_utc_offset": _OFFSET, "duration": "PT30M"}

        # Act
        fix(db, _workouts_api({"EX1": late}), dry_run=False)
        db.commit()

        # Assert
        assert set(pop_dirty_days(100)) == {(source.id, date(2026, 9, 12)), (source.id, date(2026, 9, 13))}

    def test_refreshes_the_coverage_of_the_moved_workouts(self, db: Session) -> None:
        # Arrange
        _, source = _stale_workout(db, "EX1")

        # Act
        with patch.object(_module, "data_type_coverage_repository") as coverage:
            fix(db, _workouts_api({"EX1": _polar_json()}), dry_run=False)

        # Assert
        [keys] = [call.args[1] for call in coverage.refresh_events.call_args_list]
        assert set(keys) == {(source.user_id, "polar", "workout")}


class TestRecording:
    def test_a_run_is_recorded_as_done_unless_dry(self, db: Session) -> None:
        _stale_workout(db, "EX1")
        api = _workouts_api({"EX1": _polar_json()})

        assert migrate(db, api, dry_run=True) is False
        assert migrate(db, api, dry_run=False) is True
