"""Tests for the one-off correction of Polar workout times.

The script moves stored rows onto their corrected UTC time. Two things can go wrong
that plain arithmetic would not show: a sync on the fixed code may already have
inserted the corrected copy (so moving the stale row collides on the unique key), and
a transient Polar failure must not quietly leave a row that the next sync will
duplicate. See scripts/data_migrations/fix_polar_workout_utc_offset.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

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


fix = _load_module().fix_polar_workout_times

# Polar says 09:20 local at +2, so the truth is 07:20 UTC. The old code stored 11:20.
_LOCAL = "2026-09-12T09:20:47"
_OFFSET = 120
_DURATION = timedelta(seconds=4412)
_STALE_START = datetime(2026, 9, 12, 11, 20, 47, tzinfo=timezone.utc)
_TRUE_START = datetime(2026, 9, 12, 7, 20, 47, tzinfo=timezone.utc)


def _workouts_api(responses: dict[str, Any]) -> MagicMock:
    """A PolarWorkouts stand-in: real offset maths, canned Polar responses by exercise id."""
    from app.services.providers.polar.workouts import PolarWorkouts

    api = MagicMock()
    api._extract_dates_with_offset = PolarWorkouts._extract_dates_with_offset.__get__(api)

    def detail(_db: Session, _user_id: UUID, exercise_id: str) -> dict:
        response = responses[exercise_id]
        if isinstance(response, Exception):
            raise response
        return response

    api.get_exercise_detail.side_effect = detail
    return api


def _polar_json() -> dict:
    return {"start_time": _LOCAL, "start_time_utc_offset": _OFFSET, "duration": "PT4412S"}


def _stale_workout(db: Session, external_id: str, *, active: bool = True) -> tuple[EventRecord, Any]:
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
        start_datetime=_STALE_START,
        end_datetime=_STALE_START + _DURATION,
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
    @pytest.mark.parametrize("status_code", [401, 403, 404])
    def test_statuses_the_sync_cannot_fetch_either_are_skipped(self, db: Session, status_code: int) -> None:
        # Arrange
        skipped, _ = _stale_workout(db, "GONE")
        fixed, _ = _stale_workout(db, "EX1")
        api = _workouts_api({"GONE": HTTPException(status_code=status_code), "EX1": _polar_json()})

        # Act
        counts = fix(db, api, dry_run=False)

        # Assert — the rest still gets corrected
        db.expire_all()
        assert _start_of(db, skipped.id) == _STALE_START
        assert _start_of(db, fixed.id) == _TRUE_START
        assert counts["unfetchable"] == 1

    def test_any_other_failure_aborts(self, db: Session) -> None:
        """Skipping a row the next sync CAN fetch would leave it to be duplicated."""
        # Arrange
        _stale_workout(db, "FLAKY")
        api = _workouts_api({"FLAKY": HTTPException(status_code=502)})

        # Act / Assert
        with pytest.raises(HTTPException):
            fix(db, api, dry_run=False)

    def test_users_without_an_active_connection_are_not_called(self, db: Session) -> None:
        """The sync will not fetch them, and every call would only 401."""
        # Arrange
        record, _ = _stale_workout(db, "EX1", active=False)
        api = _workouts_api({})

        # Act
        fix(db, api, dry_run=False)

        # Assert
        api.get_exercise_detail.assert_not_called()
        db.expire_all()
        assert _start_of(db, record.id) == _STALE_START
