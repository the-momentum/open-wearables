"""Regression tests: Polar 247 sync blocks must be DB-session-isolated.

Before this fix, a DB error in daily_activity would put the SQLAlchemy session
into a failed-transaction state; sleep and continuous-HR both shared the same
session (it's a FastAPI request-scoped dependency) and cascaded to the same
failure. These tests lock down the invariant that a crash in one data type
does not prevent the other two from running.
"""

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.providers.polar.data_247 import PolarData247Template
from app.services.providers.polar.strategy import PolarStrategy


@pytest.fixture
def data_247() -> PolarData247Template:
    return PolarStrategy().data_247


class TestSessionIsolation:
    def test_daily_activity_failure_rolls_back_and_sleep_runs(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        db = MagicMock()

        # Daily activity save explodes — simulate a poisoned session
        def boom(*args: Any, **kwargs: Any) -> int:
            raise RuntimeError("daily_activity save crashed")

        monkeypatch.setattr(data_247, "get_daily_activity_statistics", lambda *a, **k: [{}])
        monkeypatch.setattr(data_247, "normalize_daily_activity", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_daily_activity_statistics", boom)

        # Sleep should still run — return one synthetic synced row
        monkeypatch.setattr(data_247, "get_sleep_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_sleep", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_sleep_data", lambda *a, **k: 3)

        # HR too
        monkeypatch.setattr(data_247, "get_continuous_hr_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_continuous_hr", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "save_continuous_hr", lambda *a, **k: 7)

        results = data_247.load_and_save_all(db=db, user_id=uuid4())

        assert results["daily_activity_synced"] == 0
        assert results["sleep_sessions_synced"] == 3
        assert results["continuous_hr_synced"] == 7
        # Rollback must have been called at least once to clear the poisoned state
        assert db.rollback.called

    def test_sleep_failure_rolls_back_and_hr_runs(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        db = MagicMock()

        monkeypatch.setattr(data_247, "get_daily_activity_statistics", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_daily_activity", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_daily_activity_statistics", lambda *a, **k: 5)

        def sleep_boom(*args: Any, **kwargs: Any) -> int:
            raise RuntimeError("sleep save crashed")

        monkeypatch.setattr(data_247, "get_sleep_data", lambda *a, **k: [{}])
        monkeypatch.setattr(data_247, "normalize_sleep", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_sleep_data", sleep_boom)

        monkeypatch.setattr(data_247, "get_continuous_hr_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_continuous_hr", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "save_continuous_hr", lambda *a, **k: 9)

        results = data_247.load_and_save_all(db=db, user_id=uuid4())

        assert results["daily_activity_synced"] == 5
        assert results["sleep_sessions_synced"] == 0
        assert results["continuous_hr_synced"] == 9
        assert db.rollback.called

    def test_continuous_hr_failure_rolls_back_and_nightly_recharge_runs(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        db = MagicMock()

        monkeypatch.setattr(data_247, "get_daily_activity_statistics", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_daily_activity", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_daily_activity_statistics", lambda *a, **k: 2)

        monkeypatch.setattr(data_247, "get_sleep_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_sleep", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_sleep_data", lambda *a, **k: 4)

        def hr_boom(*args: Any, **kwargs: Any) -> int:
            raise RuntimeError("continuous HR save crashed")

        monkeypatch.setattr(data_247, "get_continuous_hr_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_continuous_hr", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "save_continuous_hr", hr_boom)

        monkeypatch.setattr(data_247, "load_and_save_recovery", lambda *a, **k: 11)

        results = data_247.load_and_save_all(db=db, user_id=uuid4())

        assert results["daily_activity_synced"] == 2
        assert results["sleep_sessions_synced"] == 4
        assert results["continuous_hr_synced"] == 0
        assert results["nightly_recharge_synced"] == 11
        assert db.rollback.called

    def test_nightly_recharge_failure_does_not_poison_previous_blocks(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        """A crash in the Phase 3 block must not undo the earlier synced counts."""
        db = MagicMock()

        monkeypatch.setattr(data_247, "get_daily_activity_statistics", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_daily_activity", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_daily_activity_statistics", lambda *a, **k: 3)

        monkeypatch.setattr(data_247, "get_sleep_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_sleep", lambda *a, **k: {})
        monkeypatch.setattr(data_247, "save_sleep_data", lambda *a, **k: 5)

        monkeypatch.setattr(data_247, "get_continuous_hr_data", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "normalize_continuous_hr", lambda *a, **k: [])
        monkeypatch.setattr(data_247, "save_continuous_hr", lambda *a, **k: 7)

        def recharge_boom(*args: Any, **kwargs: Any) -> int:
            raise RuntimeError("nightly recharge save crashed")

        monkeypatch.setattr(data_247, "load_and_save_recovery", recharge_boom)

        results = data_247.load_and_save_all(db=db, user_id=uuid4())

        assert results["daily_activity_synced"] == 3
        assert results["sleep_sessions_synced"] == 5
        assert results["continuous_hr_synced"] == 7
        assert results["nightly_recharge_synced"] == 0
        assert db.rollback.called
