# patch_id:        fix-garmin-connect-rate-limit-backoff
# status:          RETIRED 2026-09-13 — moved into backend/app/services/providers/garmin_connect/
#                  {client.py,data_247.py}. Not loaded by apply.py. Kept for history only.
#                  Reason: both targets are fork-owned, and this copy shadowed the VO2max
#                  sync added to load_and_save_all on 2026-08-29 (FORK.md §2).
# upstream_file:   backend/app/services/providers/garmin_connect/client.py, backend/app/services/providers/garmin_connect/data_247.py
# upstream_symbol: GarminConnectClient._login + ._get_api + ._call_with_reauth, GarminConnect247Data.load_and_save_all
# retire_when:     GarminConnectClient distinguishes rate-limit/Cloudflare rejections from ordinary auth failures and stops re-attempting login once blocked, AND load_and_save_all aborts the run instead of continuing through every remaining (date, data_type) pair. Marker: presence of `GarminConnectRateLimitError` (or equivalent 429-specific exception) in backend/app/services/providers/garmin_connect/.

"""Stop the Garmin Connect sync from hammering Garmin into an IP-level ban.

Bug
---
`GarminConnect247Data.load_and_save_all` loops over every calendar date in the
sync window and, for each date, over all five per-day data types::

    for cdate in self.client.iter_dates(start_date, end_date):   # ~30 days
        for data_type, fn in per_day_tasks.items():               # x 5 types
            try:
                results[data_type] += fn(cdate)
            except Exception as exc:                              # <-- swallows everything
                log_structured(..., f"Failed to sync {data_type} for {cdate}")

The blanket `except Exception` cannot distinguish "Garmin has no stress data for
this day" from "Garmin is refusing us at the IP level", so it logs and carries
on to the next pair.

That interacts catastrophically with `GarminConnectClient`. `_get_api` caches
the authenticated handle on `self._api`, but only ever assigns it *after* a
successful `_login()`. When login fails, `_api` stays `None`, so the next call
re-enters `_get_api` and re-attempts a full login. The underlying
`garminconnect` client tries five strategies per login (mobile+cffi,
mobile+requests, widget+cffi, portal+cffi, portal+requests) and sleeps ~16-20s
inside the portal strategy before giving up.

So one 30-day run costs up to 30 x 5 = 150 logins, ~750 authentication requests,
and hours of wall-clock — and Celery beat fires it hourly, so runs overlap and
compound. Once Garmin starts answering 429, every one of those requests is a
fresh 429, which is precisely how a soft rate-limit escalates into a sustained
IP block. Observed 2026-08-20: every hourly run finishing `partial`, data stuck
since 2026-08-03, logs a solid wall of::

    mobile+requests returned 429: Mobile login returned 429 - IP rate limited by Garmin
    portal+cffi returned 429: Portal login GET returned 429 - Cloudflare blocking
    Portal login: waiting 18s to avoid Cloudflare rate limiting...
    All login strategies exhausted: HTTP 403 (Cloudflare bot challenge)

Two secondary faults made it worse:

1. `_call_with_reauth` classifies an error as an auth error if the message
   contains any of ("token", "auth", "401", "403", "expired", "session",
   "login") and then re-logs-in once. A Cloudflare 403 and the wrapper's own
   "Garmin Connect authentication failed: ..." text both match, so a
   rate-limited call spent *two* login storms instead of one.
2. Nothing was persisted about being blocked, so the next scheduled run started
   from scratch a few minutes later.

Fix
---
Three coordinated changes, all reversible by flipping this patch off:

**1. Classify rate-limiting as its own failure mode.** `GarminConnectRateLimitError`
(a `GarminConnectClientError` subclass) is raised when a failure looks like a
429 / Cloudflare challenge / exhausted-strategies rejection rather than a
genuine credential problem. `_call_with_reauth` never re-authenticates on it.

**2. Fail fast, locally and globally.** On a rate-limit the client records
(a) an in-process `_blocked_until` so the remaining ~149 iterations of the
current run raise immediately without touching the network, and (b) a Redis
cooldown key so *subsequent scheduled runs* skip entirely instead of
re-hammering. The cooldown escalates geometrically per consecutive hit
(30m -> 1h -> 2h -> 4h, capped at 6h) and resets on the first success — this is
the part that actually stops the hourly loop.

**3. Abort the run, don't limp through it.** `load_and_save_all` checks the
cooldown before starting, and breaks out of *both* loops on the first
`GarminConnectRateLimitError` rather than swallowing it 149 more times. It then
re-raises so the sync run is recorded as failed instead of silently `partial`
with zero records — the same honesty fix applied to Ultrahuman's refresh path.

Genuinely transient errors (5xx, connection resets) still retry, but now with
bounded exponential backoff plus jitter, honouring `Retry-After` when present.

Per-day errors that are *not* rate-limiting (a day with no stress data, one
malformed payload) are still swallowed and logged exactly as before, so a single
bad day cannot poison a run.

Scope guards
------------
- Redis is best-effort: if it is unreachable the in-process guard still applies,
  so the patch degrades to "one wasted login per run" rather than failing.
- `_sleep` is module-level and injectable so tests don't actually wait.
- No change to what gets persisted, only to when we stop asking for it.
"""

from __future__ import annotations

import random
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import UUID

from app.database import DbSession
from app.utils.structured_logging import log_structured

_PROVIDER = "garmin_connect"

# --- Redis keys -------------------------------------------------------------
_COOLDOWN_KEY = "garmin_connect:rate_limit_cooldown"
_STRIKES_KEY = "garmin_connect:rate_limit_strikes"

# --- Cooldown schedule ------------------------------------------------------
# Geometric escalation per consecutive rate-limit, capped. The first hit already
# buys 30 minutes, which is what breaks the hourly beat loop.
_BASE_COOLDOWN_SECONDS = 30 * 60
_MAX_COOLDOWN_SECONDS = 6 * 3600
_STRIKES_TTL_SECONDS = 24 * 3600

# --- Transient retry policy -------------------------------------------------
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 2.0
_MAX_BACKOFF_SECONDS = 30.0
_JITTER_FRACTION = 0.25

# Substrings that mean "the door is shut", not "your password is wrong".
_RATE_LIMIT_MARKERS = (
    "429",
    "too many requests",
    "rate limit",
    "rate-limit",
    "ip rate limited",
    "cloudflare",
    "bot challenge",
    "strategies exhausted",
    "temporarily blocked",
    "access denied",
)

# Only these mean "re-authenticate"; deliberately narrower than upstream's list,
# which matched "403" and "login" and therefore matched Cloudflare rejections.
_AUTH_MARKERS = ("token", "unauthorized", "401", "expired", "session")

# Garmin locks an account after sustained failed logins. It surfaces as
# ACCOUNT_LOCKED / generalLoginAccountLocked in the strategy payload, and
# thereafter every login returns a misleading "401 Unauthorized (Invalid
# Username or Password)". Retrying is worse than useless: continued attempts
# keep the lock alive. Treat it as a hard stop with a cooldown.
_ACCOUNT_LOCKED_MARKERS = (
    "account_locked",
    "accountlocked",
    "generalloginaccountlocked",
)

_RETRY_AFTER_RE = re.compile(r"retry[-\s]?after[\"':=\s]+(\d+)", re.IGNORECASE)


def _sleep(seconds: float) -> None:
    """Indirection so tests can monkeypatch the wait."""
    time.sleep(seconds)


def _is_rate_limited(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _RATE_LIMIT_MARKERS)


def _is_account_locked(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _ACCOUNT_LOCKED_MARKERS)


def _is_auth_error(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _AUTH_MARKERS)


def _retry_after_seconds(message: str) -> float | None:
    match = _RETRY_AFTER_RE.search(message)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with symmetric jitter. attempt is 1-based."""
    raw = min(_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), _MAX_BACKOFF_SECONDS)
    jitter = raw * _JITTER_FRACTION
    return max(0.0, raw + random.uniform(-jitter, jitter))  # noqa: S311 - not cryptographic


# ---------------------------------------------------------------------------
# Redis-backed cooldown (best effort — never let Redis break a sync)
# ---------------------------------------------------------------------------


def _redis() -> Any | None:
    try:
        from app.integrations.redis_client import get_redis_client  # noqa: PLC0415

        return get_redis_client()
    except Exception:
        return None


def cooldown_remaining() -> int:
    """Seconds left on the global Garmin Connect cooldown, 0 if not blocked."""
    client = _redis()
    if client is None:
        return 0
    try:
        ttl = client.ttl(_COOLDOWN_KEY)
    except Exception:
        return 0
    return ttl if isinstance(ttl, int) and ttl > 0 else 0


def _record_rate_limit(logger: Any) -> int:
    """Escalate and persist the cooldown. Returns the cooldown length in seconds."""
    client = _redis()
    strikes = 1
    if client is not None:
        try:
            strikes = int(client.incr(_STRIKES_KEY))
            client.expire(_STRIKES_KEY, _STRIKES_TTL_SECONDS)
        except Exception:
            strikes = 1

    cooldown = min(_BASE_COOLDOWN_SECONDS * (2 ** (strikes - 1)), _MAX_COOLDOWN_SECONDS)

    if client is not None:
        try:
            client.setex(_COOLDOWN_KEY, cooldown, str(int(time.time()) + cooldown))
        except Exception:
            pass

    log_structured(
        logger,
        "error",
        "Garmin Connect rate limited; backing off",
        action="garmin_connect_rate_limited",
        provider=_PROVIDER,
        consecutive_strikes=strikes,
        cooldown_seconds=cooldown,
    )
    return cooldown


def _clear_rate_limit() -> None:
    client = _redis()
    if client is None:
        return
    try:
        client.delete(_COOLDOWN_KEY, _STRIKES_KEY)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GarminConnectClient replacements
# ---------------------------------------------------------------------------


def _blocked_for(self) -> int:
    """Seconds remaining before this client may talk to Garmin again."""
    until = getattr(self, "_blocked_until", 0.0)
    remaining = int(until - time.monotonic())
    if remaining > 0:
        return remaining
    return cooldown_remaining()


def _login(self, api: Any) -> None:
    """Replacement for GarminConnectClient._login with rate-limit classification."""
    from app.services.providers.garmin_connect.client import (  # noqa: PLC0415
        GarminConnectClientError,
        GarminConnectRateLimitError,
    )

    try:
        api.login()
    except Exception as exc:
        message = str(exc)
        if _is_account_locked(message):
            cooldown = _record_rate_limit(_module_logger())
            self._blocked_until = time.monotonic() + cooldown
            raise GarminConnectClientError(
                f"Garmin Connect account is LOCKED — stop retrying and unlock it at "
                f"garmin.com (password reset). Backing off {cooldown}s: {message}"
            ) from exc
        if _is_rate_limited(message):
            cooldown = _record_rate_limit(_module_logger())
            self._blocked_until = time.monotonic() + cooldown
            raise GarminConnectRateLimitError(
                f"Garmin Connect rate limited, backing off {cooldown}s: {message}"
            ) from exc
        raise GarminConnectClientError(f"Garmin Connect authentication failed: {message}") from exc

    token_path = self._token_store_path()
    token_path.mkdir(parents=True, exist_ok=True)
    api.client.dump(str(token_path))
    self._blocked_until = 0.0
    _clear_rate_limit()
    log_structured(
        _module_logger(),
        "info",
        "Garmin Connect login successful, session saved",
        provider=_PROVIDER,
    )


def _get_api(self) -> Any:
    """Replacement for GarminConnectClient._get_api that refuses to retry while blocked."""
    from app.services.providers.garmin_connect.client import (  # noqa: PLC0415
        GarminConnectRateLimitError,
    )

    if self._api is not None:
        return self._api

    blocked = _blocked_for(self)
    if blocked > 0:
        raise GarminConnectRateLimitError(
            f"Garmin Connect is in rate-limit cooldown for another {blocked}s; not attempting login"
        )

    api = self._build_api()
    if not self._try_load_saved_session(api):
        self._login(api)
    self._api = api
    return self._api


def _call_with_reauth(self, fn_name: str, *args: Any, **kwargs: Any) -> Any:
    """Replacement with rate-limit awareness and bounded backoff.

    Ordering matters: rate-limit is checked *before* auth, because a Cloudflare
    403 matches both and must never trigger a re-login.
    """
    from app.services.providers.garmin_connect.client import (  # noqa: PLC0415
        GarminConnectRateLimitError,
    )

    reauthed = False
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        api = self._get_api()
        try:
            return getattr(api, fn_name)(*args, **kwargs)
        except GarminConnectRateLimitError:
            raise
        except Exception as exc:
            last_exc = exc
            message = str(exc)

            if _is_rate_limited(message):
                cooldown = _record_rate_limit(_module_logger())
                self._blocked_until = time.monotonic() + cooldown
                raise GarminConnectRateLimitError(
                    f"Garmin Connect rate limited during {fn_name}, backing off {cooldown}s: {message}"
                ) from exc

            if _is_auth_error(message) and not reauthed:
                reauthed = True
                log_structured(
                    _module_logger(),
                    "warning",
                    "Garmin Connect session expired, re-authenticating",
                    provider=_PROVIDER,
                    error=message,
                )
                self._api = None
                continue

            if attempt >= _MAX_ATTEMPTS:
                raise

            delay = _retry_after_seconds(message) or _backoff_delay(attempt)
            log_structured(
                _module_logger(),
                "warning",
                f"Garmin Connect {fn_name} failed, retrying after backoff",
                action="garmin_connect_transient_retry",
                provider=_PROVIDER,
                attempt=attempt,
                max_attempts=_MAX_ATTEMPTS,
                delay_seconds=round(delay, 2),
                error=message,
            )
            _sleep(delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Garmin Connect {fn_name} exhausted retries without an exception")


def _module_logger() -> Any:
    import logging  # noqa: PLC0415

    return logging.getLogger("app.services.providers.garmin_connect.client")


# ---------------------------------------------------------------------------
# GarminConnect247Data.load_and_save_all replacement
# ---------------------------------------------------------------------------


def load_and_save_all(
    self,
    db: DbSession,
    user_id: UUID,
    start_time: datetime | str | None = None,
    end_time: datetime | str | None = None,
    is_first_sync: bool = False,
) -> dict[str, int]:
    """Replacement that aborts on rate-limit instead of grinding through every pair."""
    from datetime import timedelta  # noqa: PLC0415

    from app.services.providers.garmin_connect.client import (  # noqa: PLC0415
        GarminConnectClientError,
        GarminConnectRateLimitError,
    )

    blocked = cooldown_remaining()
    if blocked > 0:
        log_structured(
            self.logger,
            "warning",
            "Skipping Garmin Connect 24/7 sync: rate-limit cooldown active",
            action="garmin_connect_sync_skipped_cooldown",
            cooldown_remaining_seconds=blocked,
            user_id=str(user_id),
        )
        raise GarminConnectRateLimitError(
            f"Garmin Connect is in rate-limit cooldown for another {blocked}s; sync skipped"
        )

    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    if not start_time:
        start_time = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_time:
        end_time = datetime.now(timezone.utc)

    start_date = start_time.date()
    end_date = end_time.date()

    results: dict[str, int] = {
        "sleep": 0,
        "heart_rate": 0,
        "daily_stats": 0,
        "stress": 0,
        "hrv": 0,
    }

    per_day_tasks: dict[str, Callable[[date], int]] = {
        "sleep": lambda d: self.save_sleep_for_date(db, user_id, d),
        "heart_rate": lambda d: self.save_heart_rate_for_date(db, user_id, d),
        "daily_stats": lambda d: self.save_daily_stats_for_date(db, user_id, d),
        "stress": lambda d: self.save_stress_for_date(db, user_id, d),
        "hrv": lambda d: self.save_hrv_for_date(db, user_id, d),
    }

    # Any GarminConnectClientError is unrecoverable for the rest of this run:
    # a rate limit, a locked account, or wrong credentials will all still be true
    # on the next (date, data_type) pair. Only genuinely per-day errors continue.
    fatal_exc: Exception | None = None

    for cdate in self.client.iter_dates(start_date, end_date):
        if fatal_exc is not None:
            break
        for data_type, fn in per_day_tasks.items():
            try:
                results[data_type] += fn(cdate)
            except GarminConnectClientError as exc:
                # Abort the whole run. Continuing would issue one more login
                # storm per remaining (date, data_type) pair — which is how a
                # soft rate-limit became an IP block and then a locked account.
                fatal_exc = exc
                rate_limited = isinstance(exc, GarminConnectRateLimitError)
                log_structured(
                    self.logger,
                    "error",
                    "Aborting Garmin Connect 24/7 sync: "
                    + ("rate limited" if rate_limited else "authentication failed"),
                    action="garmin_connect_sync_aborted_rate_limit"
                    if rate_limited
                    else "garmin_connect_sync_aborted_auth",
                    data_type=data_type,
                    date=str(cdate),
                    error=str(exc),
                    partial_results=dict(results),
                    user_id=str(user_id),
                )
                break
            except Exception as exc:
                log_structured(
                    self.logger,
                    "error",
                    f"Failed to sync {data_type} for {cdate}",
                    action="garmin_connect_sync_error",
                    data_type=data_type,
                    date=str(cdate),
                    error=str(exc),
                    user_id=str(user_id),
                )

    if fatal_exc is not None:
        # Surface as a failure so the sync run isn't recorded as a successful
        # no-op. Records already persisted stay persisted.
        raise fatal_exc

    try:
        results["body_composition"] = self.save_body_composition(db, user_id, start_date, end_date)
    except GarminConnectClientError as exc:
        results["body_composition"] = 0
        raise exc
    except Exception as exc:
        results["body_composition"] = 0
        log_structured(
            self.logger,
            "error",
            "Failed to sync body composition data",
            action="garmin_connect_body_comp_sync_error",
            error=str(exc),
            user_id=str(user_id),
        )

    return results


def install() -> None:
    """Install rate-limit classification, backoff, and run-abort behaviour."""
    import sys  # noqa: PLC0415

    import app.services.providers.garmin_connect.client  # noqa: F401, PLC0415
    import app.services.providers.garmin_connect.data_247  # noqa: F401, PLC0415

    client_module = sys.modules["app.services.providers.garmin_connect.client"]
    data_247_module = sys.modules["app.services.providers.garmin_connect.data_247"]

    # Define the exception on the client module so both the module and any
    # `from ... import GarminConnectRateLimitError` site resolve to one class.
    if not hasattr(client_module, "GarminConnectRateLimitError"):

        class GarminConnectRateLimitError(client_module.GarminConnectClientError):
            """Raised when Garmin is refusing requests at the rate-limit/WAF layer."""

        client_module.GarminConnectRateLimitError = GarminConnectRateLimitError

    client_module.GarminConnectClient._login = _login
    client_module.GarminConnectClient._get_api = _get_api
    client_module.GarminConnectClient._call_with_reauth = _call_with_reauth
    client_module.GarminConnectClient._blocked_for = _blocked_for

    data_247_module.GarminConnect247Data.load_and_save_all = load_and_save_all
