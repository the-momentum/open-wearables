"""Tests for the Garmin Connect rate-limit backoff (formerly the fix-garmin-connect-rate-limit-backoff ow-patch).

Regression cover for the bug where a Garmin 429 / Cloudflare rejection was
treated as a recoverable per-(date, data_type) error, causing ~150 full login
attempts per sync run and escalating a soft rate-limit into an IP-level block.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.services.providers.garmin_connect import client as garmin_client
from app.services.providers.garmin_connect.client import (
    GarminConnectClient,
    GarminConnectClientError,
)
from app.services.providers.garmin_connect.data_247 import GarminConnect247Data


@pytest.fixture(scope="module")
def patch_module() -> Any:
    """The module that owns the rate-limit machinery.

    Until 2026-09-13 this was the ow-patch
    ``_ow_patches_fix_garmin_connect_rate_limit_backoff``; the behaviour now lives
    in ``garmin_connect/client.py`` directly (the patch shadowed the fork's own
    later edits to ``load_and_save_all``). The fixture name is kept so the tests
    below read unchanged — they monkeypatch ``_redis`` / ``_sleep`` /
    ``cooldown_remaining`` on whichever module owns them.
    """
    assert sys.modules["app.services.providers.garmin_connect.client"] is garmin_client
    return garmin_client


@pytest.fixture
def no_redis(monkeypatch: pytest.MonkeyPatch, patch_module: Any) -> None:
    """Force the Redis helpers to be unavailable so tests exercise the in-process guard."""
    monkeypatch.setattr(patch_module, "_redis", lambda: None)


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch, patch_module: Any) -> list[float]:
    """Capture backoff delays instead of actually waiting."""
    delays: list[float] = []
    monkeypatch.setattr(patch_module, "_sleep", delays.append)
    return delays


class TestRateLimitClassification:
    """The 429/WAF markers must be distinguished from ordinary auth failures."""

    @pytest.mark.parametrize(
        "message",
        [
            "Mobile login returned 429 - IP rate limited by Garmin",
            "Portal login GET returned 429 - Cloudflare blocking this request",
            "Login failed: All login strategies exhausted: HTTP 403 (Cloudflare bot challenge)",
            "429 Too Many Requests",
            "Access denied",
        ],
    )
    def test_rate_limit_markers_detected(self, patch_module: Any, message: str) -> None:
        assert patch_module._is_rate_limited(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "Invalid credentials",
            "KeyError: 'sleepMovement'",
            "Connection reset by peer",
        ],
    )
    def test_non_rate_limit_messages_ignored(self, patch_module: Any, message: str) -> None:
        assert patch_module._is_rate_limited(message) is False

    def test_cloudflare_403_is_not_treated_as_auth_error(self, patch_module: Any) -> None:
        """Upstream's auth-marker list matched '403' and 'login', which is the bug."""
        message = "All login strategies exhausted: HTTP 403 (Cloudflare bot challenge)"
        assert patch_module._is_rate_limited(message) is True
        assert patch_module._is_auth_error(message) is False

    def test_retry_after_is_parsed(self, patch_module: Any) -> None:
        assert patch_module._retry_after_seconds("rejected, Retry-After: 120") == 120.0
        assert patch_module._retry_after_seconds("no hint here") is None


class TestBackoff:
    def test_backoff_grows_and_is_capped(self, patch_module: Any) -> None:
        first = patch_module._backoff_delay(1)
        later = patch_module._backoff_delay(4)
        assert first <= later
        assert patch_module._backoff_delay(50) <= patch_module._MAX_BACKOFF_SECONDS * (
            1 + patch_module._JITTER_FRACTION
        )

    def test_backoff_is_never_negative(self, patch_module: Any) -> None:
        assert all(patch_module._backoff_delay(n) >= 0.0 for n in range(1, 8))


class TestLoginStopsRetrying:
    """A rate-limited client must not attempt a second login."""

    def test_login_raises_rate_limit_error_and_blocks(self, patch_module: Any, no_redis: None) -> None:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        client = GarminConnectClient()
        attempts = {"count": 0}

        class FakeApi:
            def login(self) -> None:
                attempts["count"] += 1
                raise RuntimeError("Mobile login returned 429 - IP rate limited by Garmin")

        with pytest.raises(GarminConnectRateLimitError):
            client._login(FakeApi())

        assert attempts["count"] == 1
        assert client._blocked_for() > 0

    def test_get_api_refuses_to_login_while_blocked(
        self, patch_module: Any, no_redis: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        client = GarminConnectClient()
        client._blocked_until = patch_module.time.monotonic() + 600

        def explode() -> Any:
            raise AssertionError("_build_api must not be called while blocked")

        monkeypatch.setattr(client, "_build_api", explode)

        with pytest.raises(GarminConnectRateLimitError):
            client._get_api()

    def test_genuine_auth_failure_still_raises_client_error(self, patch_module: Any, no_redis: None) -> None:
        client = GarminConnectClient()

        class FakeApi:
            def login(self) -> None:
                raise RuntimeError("Invalid credentials")

        with pytest.raises(GarminConnectClientError) as exc_info:
            client._login(FakeApi())

        assert "authentication failed" in str(exc_info.value)
        assert client._blocked_for() == 0


class TestCallWithReauthDoesNotReauthOnRateLimit:
    def test_rate_limit_does_not_trigger_reauth(self, patch_module: Any, no_redis: None, no_sleep: list[float]) -> None:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        client = GarminConnectClient()
        logins = {"count": 0}

        class FakeApi:
            def get_sleep_data(self, _cdate: str) -> dict:
                raise RuntimeError("returned 429 - IP rate limited by Garmin")

        client._api = FakeApi()

        def fake_login(_api: Any) -> None:
            logins["count"] += 1

        client._login = fake_login  # type: ignore[method-assign]

        with pytest.raises(GarminConnectRateLimitError):
            client._call_with_reauth("get_sleep_data", "2026-08-06")

        assert logins["count"] == 0, "must not re-authenticate against a rate limit"
        assert no_sleep == [], "must not burn backoff waits on a rate limit"

    def test_transient_error_retries_with_backoff(
        self, patch_module: Any, no_redis: None, no_sleep: list[float]
    ) -> None:
        client = GarminConnectClient()
        calls = {"count": 0}

        class FakeApi:
            def get_stats(self, _cdate: str) -> dict:
                calls["count"] += 1
                if calls["count"] < 3:
                    raise RuntimeError("Connection reset by peer")
                return {"steps": 1234}

        client._api = FakeApi()

        result = client._call_with_reauth("get_stats", "2026-08-06")

        assert result == {"steps": 1234}
        assert calls["count"] == 3
        assert len(no_sleep) == 2, "should have backed off between attempts"


class TestLoadAndSaveAllAborts:
    """The core regression: one rate limit must end the run, not 149 more logins."""

    def _make_handler(self, patch_module: Any, failing: bool) -> tuple[GarminConnect247Data, dict]:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        counters = {"calls": 0}

        class FakeClient:
            def iter_dates(self, start: Any, end: Any) -> list[Any]:
                from datetime import timedelta

                out = []
                cur = start
                while cur <= end:
                    out.append(cur)
                    cur += timedelta(days=1)
                return out

        handler = GarminConnect247Data(
            provider_name="garmin_connect",
            api_base_url="https://connect.garmin.com",
            client=FakeClient(),
        )

        def bump(_db: Any, _uid: Any, _d: Any) -> int:
            counters["calls"] += 1
            if failing:
                raise GarminConnectRateLimitError("returned 429 - IP rate limited by Garmin")
            return 1

        for name in (
            "save_sleep_for_date",
            "save_heart_rate_for_date",
            "save_daily_stats_for_date",
            "save_stress_for_date",
            "save_hrv_for_date",
        ):
            setattr(handler, name, bump)
        handler.save_body_composition = lambda *_a, **_k: 0  # type: ignore[method-assign]
        handler.save_vo2max_for_range = lambda *_a, **_k: 0  # type: ignore[method-assign]

        return handler, counters

    def test_aborts_after_first_rate_limit(self, patch_module: Any, no_redis: None) -> None:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        handler, counters = self._make_handler(patch_module, failing=True)

        with pytest.raises(GarminConnectRateLimitError):
            handler.load_and_save_all(
                db=SimpleNamespace(),  # type: ignore[arg-type]
                user_id=uuid4(),
                start_time=datetime(2026, 7, 20, tzinfo=timezone.utc),
                end_time=datetime(2026, 8, 20, tzinfo=timezone.utc),
            )

        # Pre-patch this would have been 32 days x 5 types = 160 calls, each a
        # full five-strategy login storm.
        assert counters["calls"] == 1, f"expected to abort on first failure, made {counters['calls']} calls"

    def test_healthy_run_still_visits_every_pair(self, patch_module: Any, no_redis: None) -> None:
        handler, counters = self._make_handler(patch_module, failing=False)

        results = handler.load_and_save_all(
            db=SimpleNamespace(),  # type: ignore[arg-type]
            user_id=uuid4(),
            start_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )

        assert counters["calls"] == 3 * 5
        assert results["sleep"] == 3

    def test_ordinary_per_day_error_is_still_swallowed(self, patch_module: Any, no_redis: None) -> None:
        """A single bad day must not abort the run — unchanged from upstream."""
        handler, counters = self._make_handler(patch_module, failing=False)

        def sometimes_bad(_db: Any, _uid: Any, d: Any) -> int:
            counters["calls"] += 1
            if d.day == 2:
                raise ValueError("malformed stress payload")
            return 1

        handler.save_stress_for_date = sometimes_bad  # type: ignore[method-assign]

        results = handler.load_and_save_all(
            db=SimpleNamespace(),  # type: ignore[arg-type]
            user_id=uuid4(),
            start_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )

        assert results["stress"] == 2, "two good days should still persist"

    def test_cooldown_short_circuits_the_run(self, patch_module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.providers.garmin_connect.client import GarminConnectRateLimitError

        handler, counters = self._make_handler(patch_module, failing=False)
        monkeypatch.setattr(patch_module, "cooldown_remaining", lambda: 900)

        with pytest.raises(GarminConnectRateLimitError):
            handler.load_and_save_all(
                db=SimpleNamespace(),  # type: ignore[arg-type]
                user_id=uuid4(),
                start_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
                end_time=datetime(2026, 8, 3, tzinfo=timezone.utc),
            )

        assert counters["calls"] == 0, "must not touch Garmin at all while cooling down"


class TestCooldownEscalation:
    def test_cooldown_doubles_per_strike_and_caps(self, patch_module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        strikes = {"n": 0}

        class FakeRedis:
            def incr(self, _key: str) -> int:
                strikes["n"] += 1
                return strikes["n"]

            def expire(self, _key: str, _ttl: int) -> None:
                pass

            def setex(self, _key: str, _ttl: int, _val: str) -> None:
                pass

        monkeypatch.setattr(patch_module, "_redis", lambda: FakeRedis())

        seen = [patch_module._record_rate_limit(patch_module.logger) for _ in range(6)]

        assert seen[0] == patch_module._BASE_COOLDOWN_SECONDS
        assert seen[1] == patch_module._BASE_COOLDOWN_SECONDS * 2
        assert seen == sorted(seen), "cooldown must be non-decreasing"
        assert max(seen) <= patch_module._MAX_COOLDOWN_SECONDS


class TestAccountLockedAndAuthAbort:
    """Regression cover for the 2026-08-20 account lock.

    Weeks of hammering escalated 429 -> IP block -> ACCOUNT_LOCKED. After the
    lock, Garmin returns a misleading "401 Unauthorized (Invalid Username or
    Password)", which the classifier correctly reads as an AUTH failure, not a
    rate limit — and the original fix only aborted on rate limits, so the per-day
    loop kept re-attempting login and kept the lock alive.
    """

    @pytest.mark.parametrize(
        "message",
        [
            "{'type': 'ACCOUNT_LOCKED', 'message': 'generalLoginAccountLocked'}",
            "Mobile login failed: ACCOUNT_LOCKED",
            "generalloginaccountlocked",
        ],
    )
    def test_account_lock_detected(self, patch_module: Any, message: str) -> None:
        assert patch_module._is_account_locked(message) is True

    def test_ordinary_bad_password_is_not_a_lock(self, patch_module: Any) -> None:
        assert patch_module._is_account_locked("401 Unauthorized (Invalid Username or Password)") is False

    def test_lock_sets_cooldown_and_names_the_remedy(self, patch_module: Any, no_redis: None) -> None:
        client = GarminConnectClient()

        class FakeApi:
            def login(self) -> None:
                raise RuntimeError("Mobile login failed: {'type': 'ACCOUNT_LOCKED'}")

        with pytest.raises(GarminConnectClientError) as exc_info:
            client._login(FakeApi())

        assert "LOCKED" in str(exc_info.value)
        assert "password reset" in str(exc_info.value)
        assert client._blocked_for() > 0, "a locked account must cool down like a rate limit"

    def test_auth_failure_aborts_the_run_after_one_attempt(self, patch_module: Any, no_redis: None) -> None:
        """This is the bug the account lock exposed: 401 was swallowed per-day."""
        counters = {"calls": 0}

        class FakeClient:
            def iter_dates(self, start: Any, end: Any) -> list[Any]:
                from datetime import timedelta

                out, cur = [], start
                while cur <= end:
                    out.append(cur)
                    cur += timedelta(days=1)
                return out

        handler = GarminConnect247Data(
            provider_name="garmin_connect",
            api_base_url="https://connect.garmin.com",
            client=FakeClient(),
        )

        def bad_creds(_db: Any, _uid: Any, _d: Any) -> int:
            counters["calls"] += 1
            raise GarminConnectClientError(
                "Garmin Connect authentication failed: 401 Unauthorized (Invalid Username or Password)"
            )

        for name in (
            "save_sleep_for_date",
            "save_heart_rate_for_date",
            "save_daily_stats_for_date",
            "save_stress_for_date",
            "save_hrv_for_date",
        ):
            setattr(handler, name, bad_creds)
        handler.save_body_composition = lambda *_a, **_k: 0  # type: ignore[method-assign]
        handler.save_vo2max_for_range = lambda *_a, **_k: 0  # type: ignore[method-assign]

        with pytest.raises(GarminConnectClientError):
            handler.load_and_save_all(
                db=SimpleNamespace(),  # type: ignore[arg-type]
                user_id=uuid4(),
                start_time=datetime(2026, 7, 20, tzinfo=timezone.utc),
                end_time=datetime(2026, 8, 20, tzinfo=timezone.utc),
            )

        assert counters["calls"] == 1, (
            f"a credential failure must abort the run, not retry per (date, type); made {counters['calls']} calls"
        )
