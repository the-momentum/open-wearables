"""Tests for the Postgres-backed sleep session store + advisory lock (inline mode)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.providers.mobile_sdk import SleepState
from app.services.apple.healthkit import sleep_service
from app.services.apple.healthkit.sleep_service import (
    delete_sleep_state,
    finalize_stale_sleep_for_user,
    iter_active_user_ids,
    load_sleep_state,
    save_sleep_state,
    user_sleep_lock,
)
from tests import factories


@pytest.fixture(autouse=True)
def _inline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the Postgres sleep-state backend for these tests."""
    monkeypatch.setattr(settings, "task_execution_mode", "inline")


def _make_state(end: datetime | None = None) -> SleepState:
    end = end or datetime(2026, 3, 16, 6, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=7)
    return SleepState(
        uuid="sess-1",
        source_name="Apple Watch",
        provider="apple",
        start_time=start,
        end_time=end,
        last_start_timestamp=start,
        last_end_timestamp=end,
        deep_seconds=3600,
    )


def test_save_load_delete_roundtrip(db: Session) -> None:
    user = factories.UserFactory()
    uid = str(user.id)
    state = _make_state()

    assert load_sleep_state(db, uid) is None

    save_sleep_state(db, uid, state)
    loaded = load_sleep_state(db, uid)
    assert loaded is not None
    assert loaded.uuid == "sess-1"
    assert loaded.deep_seconds == 3600
    assert loaded.start_time == state.start_time

    assert uid in iter_active_user_ids(db)

    delete_sleep_state(db, uid)
    assert load_sleep_state(db, uid) is None
    assert uid not in iter_active_user_ids(db)


def test_save_is_upsert(db: Session) -> None:
    user = factories.UserFactory()
    uid = str(user.id)
    state = _make_state()
    save_sleep_state(db, uid, state)

    state.deep_seconds = 7200
    save_sleep_state(db, uid, state)

    loaded = load_sleep_state(db, uid)
    assert loaded is not None
    assert loaded.deep_seconds == 7200
    # Still exactly one active session for this user.
    assert iter_active_user_ids(db).count(uid) == 1


def test_advisory_lock_serializes_same_user(db: Session, engine: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # The lock uses its own connection from app.database.engine; point that at the
    # test engine so both lock connections hit the same (test) database.
    monkeypatch.setattr(sleep_service, "engine", engine)
    user = factories.UserFactory()
    uid = str(user.id)

    with user_sleep_lock(uid, wait_seconds=0) as acquired_first:
        assert acquired_first is True
        # A second acquisition for the same user must fail fast while the first holds it.
        with user_sleep_lock(uid, wait_seconds=0) as acquired_second:
            assert acquired_second is False

    # Once released, the lock can be acquired again.
    with user_sleep_lock(uid, wait_seconds=0) as acquired_again:
        assert acquired_again is True


def test_finalize_stale_sleep_for_user_finalizes_stale_state(
    db: Session, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sleep_service, "engine", engine)
    finish_sleep = MagicMock()
    monkeypatch.setattr(sleep_service, "finish_sleep", finish_sleep)
    user = factories.UserFactory()
    state = _make_state(datetime.now(timezone.utc) - timedelta(hours=3))
    save_sleep_state(db, str(user.id), state)

    finalized = finalize_stale_sleep_for_user(db, user.id)

    assert finalized is True
    finish_sleep.assert_called_once_with(db, str(user.id), state)


def test_finalize_stale_sleep_for_user_skips_recent_state(
    db: Session, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sleep_service, "engine", engine)
    finish_sleep = MagicMock()
    monkeypatch.setattr(sleep_service, "finish_sleep", finish_sleep)
    user = factories.UserFactory()
    save_sleep_state(db, str(user.id), _make_state(datetime.now(timezone.utc) - timedelta(minutes=5)))

    finalized = finalize_stale_sleep_for_user(db, user.id)

    assert finalized is False
    finish_sleep.assert_not_called()
