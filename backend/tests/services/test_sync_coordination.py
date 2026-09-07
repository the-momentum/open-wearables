"""primary_is_idle: an orphaned pull lock is one whose holder shows no live sync run.

Uses the session Redis container (autouse fixtures in tests/conftest.py); runs are recorded
through the real sync-status service so the check reads exactly what production reads.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.sync_status import SyncSource
from app.services import sync_status_service
from app.services.sync_coordination import PRIMARY_IDLE_SECONDS, primary_is_idle


def test_holder_without_any_recorded_run_is_idle() -> None:
    assert primary_is_idle("google", uuid4()) is True


def test_holder_with_fresh_in_progress_run_is_alive() -> None:
    holder = uuid4()
    sync_status_service.started(holder, "google", SyncSource.PULL, run_id="pull_fresh")
    assert primary_is_idle("google", holder) is False


def test_in_progress_run_that_stopped_reporting_is_idle() -> None:
    holder = uuid4()
    sync_status_service.started(holder, "google", SyncSource.PULL, run_id="pull_dead")
    later = datetime.now(timezone.utc) + timedelta(seconds=PRIMARY_IDLE_SECONDS + 1)
    assert primary_is_idle("google", holder, now=later) is True
    assert primary_is_idle("google", holder, now=later, idle_seconds=PRIMARY_IDLE_SECONDS + 60) is False


def test_only_terminal_runs_means_idle() -> None:
    holder = uuid4()
    sync_status_service.started(holder, "google", SyncSource.PULL, run_id="pull_done")
    sync_status_service.completed(holder, "google", SyncSource.PULL, run_id="pull_done", items_processed=3)
    assert primary_is_idle("google", holder) is True


def test_live_run_for_another_provider_does_not_count() -> None:
    holder = uuid4()
    sync_status_service.started(holder, "polar", SyncSource.PULL, run_id="pull_polar")
    assert primary_is_idle("google", holder) is True
    assert primary_is_idle("polar", holder) is False
