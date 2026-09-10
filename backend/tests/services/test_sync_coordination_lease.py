"""Lease renewal for the pull primary lock: a killed worker stops renewing and the lock frees."""

import threading
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.config import Settings, settings
from app.integrations.redis_client import get_redis_client
from app.services import sync_coordination
from app.services.sync_coordination import (
    bind_primary_lease,
    clear_primary_lease,
    lease_lost,
    release_primary,
    renew_primary,
    try_become_primary,
)

PROVIDER = "google"
PROVIDER_USER_ID = "4661043890044766408"
RENEW_INTERVAL = 0.02


def _eventually(pred: Callable[[], Any], timeout: float = 2.0) -> bool:
    """Poll a background thread's effect instead of sleeping for a fixed guess."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(RENEW_INTERVAL / 2)
    return False


class _Counter:
    """Counts renewal attempts made by the background thread."""

    def __init__(self) -> None:
        self.count = 0
        self._lock = threading.Lock()

    def hit(self, result: Any) -> Callable[..., Any]:
        def _side_effect(*_args: Any, **_kwargs: Any) -> Any:
            with self._lock:
                self.count += 1
            if isinstance(result, Exception):
                raise result
            return result

        return _side_effect

    def reached(self, n: int) -> bool:
        return _eventually(lambda: self.count >= n)


@pytest.fixture(autouse=True)
def _clean_lease() -> Generator[None, None, None]:
    clear_primary_lease()
    yield
    clear_primary_lease()


@pytest.fixture
def fast_renewal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The renewer reads the interval once at thread start, so patch it before binding."""
    monkeypatch.setattr(settings, "linked_sync_renew_interval_seconds", RENEW_INTERVAL)


@pytest.fixture
def redis_client() -> Any:
    return get_redis_client()


class TestLeaseTtl:
    def test_pull_scope_uses_the_short_lease(self) -> None:
        assert sync_coordination._ttl_for("pull") == settings.linked_sync_pull_lease_seconds
        assert sync_coordination._ttl_for("backfill") == settings.linked_sync_backfill_lease_seconds
        assert sync_coordination._ttl_for("pull") < sync_coordination._ttl_for("backfill")

    def test_acquired_pull_lock_carries_the_lease_ttl(self, redis_client: Any) -> None:
        acquired, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, uuid4(), scope="pull")
        assert acquired
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        assert 0 < redis_client.ttl(key) <= settings.linked_sync_pull_lease_seconds


class TestRenewPrimary:
    def test_renew_extends_only_our_own_lease(self, redis_client: Any) -> None:
        user_id = uuid4()
        _, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, user_id, scope="pull")
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.expire(key, 5)

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is True
        assert redis_client.ttl(key) > 5

    def test_renew_fails_once_another_profile_holds_it(self) -> None:
        user_id, token = uuid4(), "stale-token"
        try_become_primary(PROVIDER, PROVIDER_USER_ID, uuid4(), scope="pull")

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is False

    def test_renew_fails_when_the_lease_already_expired(self) -> None:
        user_id, token = uuid4(), "gone"

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is False


class TestRenewalThread:
    def test_no_thread_without_a_token(self) -> None:
        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "")

        assert sync_coordination._lease.state is None

    def test_renews_until_the_lease_is_cleared(self, fast_renewal: None) -> None:
        calls = _Counter()
        with patch.object(sync_coordination, "renew_primary", side_effect=calls.hit(True)):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            assert calls.reached(2)
            thread = sync_coordination._lease.state.thread

            clear_primary_lease()
            assert thread.is_alive() is False
            settled = calls.count
            time.sleep(RENEW_INTERVAL * 5)
            assert calls.count == settled  # a cleared lease is never renewed again

    def test_retakes_a_lapsed_lease_and_keeps_going(self, fast_renewal: None) -> None:
        calls = _Counter()
        with (
            patch.object(sync_coordination, "renew_primary", side_effect=calls.hit(False)),
            patch.object(sync_coordination, "reacquire_primary", return_value=True),
        ):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            assert calls.reached(2)
            assert lease_lost() is False

    def test_marks_the_lease_lost_and_exits(self, fast_renewal: None) -> None:
        with (
            patch.object(sync_coordination, "renew_primary", return_value=False),
            patch.object(sync_coordination, "reacquire_primary", return_value=False),
        ):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            assert _eventually(lease_lost)
            assert _eventually(lambda: not sync_coordination._lease.state.thread.is_alive())

    def test_an_unreachable_redis_does_not_drop_the_lease(self, fast_renewal: None) -> None:
        calls = _Counter()
        with patch.object(sync_coordination, "renew_primary", side_effect=calls.hit(ConnectionError("redis down"))):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            assert calls.reached(2)  # keeps trying rather than giving the lock up
            assert lease_lost() is False

    def test_a_second_bind_replaces_the_first_renewer(self, fast_renewal: None) -> None:
        with patch.object(sync_coordination, "renew_primary", return_value=True):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            first = sync_coordination._lease.state.thread
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok2")

            assert first.is_alive() is False
            assert sync_coordination._lease.state.thread is not first

    def test_lease_is_per_thread(self, fast_renewal: None) -> None:
        with patch.object(sync_coordination, "renew_primary", return_value=True):
            bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(lease_lost).result() is False  # other thread sees no lease
            assert sync_coordination._lease.state is not None


class TestRenewalAgainstRedis:
    def test_the_bound_thread_keeps_the_real_key_alive(self, fast_renewal: None, redis_client: Any) -> None:
        user_id = uuid4()
        _, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, user_id, scope="pull")
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.expire(key, 5)

        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, user_id, token)

        assert _eventually(lambda: redis_client.ttl(key) > 5)

    def test_a_dead_renewer_lets_the_key_expire(self, fast_renewal: None, redis_client: Any) -> None:
        """A killed worker takes its daemon thread with it, which is the whole point."""
        user_id = uuid4()
        _, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, user_id, scope="pull")
        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, user_id, token)
        clear_primary_lease()  # stands in for the process going away

        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.expire(key, 1)
        assert _eventually(lambda: not redis_client.exists(key), timeout=3.0)


class TestReleaseAfterLeaseLoss:
    def test_a_demoted_holder_cannot_release_the_successor_lock(self, redis_client: Any) -> None:
        first, second = uuid4(), uuid4()
        _, first_token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, first, scope="pull")
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.delete(key)  # first holder's lease lapses
        acquired, _, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, second, scope="pull")
        assert acquired

        assert release_primary(PROVIDER, PROVIDER_USER_ID, first, first_token, scope="pull") is False
        assert redis_client.exists(key)


class TestSettingsInvariant:
    """The lease must survive a missed renewal."""

    def test_a_lease_under_twice_the_interval_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least twice"):
            Settings(linked_sync_pull_lease_seconds=30, linked_sync_renew_interval_seconds=20)

    def test_defaults_leave_headroom(self) -> None:
        assert settings.linked_sync_renew_interval_seconds * 2 <= settings.linked_sync_pull_lease_seconds
