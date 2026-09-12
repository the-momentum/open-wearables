"""Garmin Connect API client wrapper using python-garminconnect."""

import logging
import random
import re
import time
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.config import settings
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PROVIDER = "garmin_connect"

# ---------------------------------------------------------------------------
# Rate-limit / account-lock handling.
#
# Formerly ow-patches/local/fix-garmin-connect-rate-limit-backoff.py, retired
# into source on 2026-09-13: this file is fork-only, so a runtime patch over it
# bought every shadowing hazard and no upstream-conflict benefit (FORK.md §2).
# The patch file is kept for its history.
#
# Why this exists: load_and_save_all loops ~30 dates x 5 data types, and the
# underlying garminconnect client walks up to five login strategies per login.
# Without classification, one 429 turned into ~150 login storms per run, hourly,
# which is how a soft rate-limit became an IP block and then a LOCKED account
# (observed 2026-08-20). See LONGEVITY.md / FORK.md §6 for the request budget.
# ---------------------------------------------------------------------------

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

# Only these mean "re-authenticate"; deliberately narrower than the original
# list, which matched "403" and "login" and therefore matched Cloudflare
# rejections — so a rate-limited call cost two login storms instead of one.
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


class GarminConnectClientError(Exception):
    """Raised when the Garmin Connect client cannot be used."""


class GarminConnectRateLimitError(GarminConnectClientError):
    """Raised when Garmin is refusing requests at the rate-limit/WAF layer.

    Distinct from a credential failure so callers never re-authenticate on it:
    a login attempt is exactly the request Garmin is rate-limiting.
    """


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


# --- Redis-backed cooldown (best effort — never let Redis break a sync) -------


def _redis() -> Any | None:
    try:
        from app.integrations.redis_client import get_redis_client  # noqa: PLC0415

        return get_redis_client()
    except Exception:
        return None


def cooldown_remaining() -> int:
    """Seconds left on the global Garmin Connect cooldown, 0 if not blocked.

    Global, not per-client: the limit Garmin applies is per IP / per account,
    and every worker shares both.
    """
    client = _redis()
    if client is None:
        return 0
    try:
        ttl = client.ttl(_COOLDOWN_KEY)
    except Exception:
        return 0
    return ttl if isinstance(ttl, int) and ttl > 0 else 0


def _record_rate_limit(log: logging.Logger) -> int:
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
        with suppress(Exception):
            client.setex(_COOLDOWN_KEY, cooldown, str(int(time.time()) + cooldown))

    log_structured(
        log,
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
    with suppress(Exception):
        client.delete(_COOLDOWN_KEY, _STRIKES_KEY)


class GarminConnectClient:
    """Thin wrapper around garminconnect.Garmin.

    Handles:
    - Login with email/password from settings
    - Token persistence to disk so re-auth is not needed on every request
    - Automatic re-authentication when the session expires
    """

    def __init__(self) -> None:
        self._api: Any = None  # garminconnect.Garmin instance
        self._device_model: str | None = None
        self._device_model_cached: bool = False
        # monotonic() deadline before which this process must not talk to Garmin.
        # Complements the Redis cooldown: this one is checked without any I/O so
        # the remaining ~149 (date, data_type) pairs of a blocked run fail instantly.
        self._blocked_until: float = 0.0

    def _get_credentials(self) -> tuple[str, str]:
        email = settings.garmin_connect_email
        password = settings.garmin_connect_password

        if not email or not password:
            raise GarminConnectClientError(
                "GARMIN_CONNECT_EMAIL and GARMIN_CONNECT_PASSWORD must be set in environment"
            )

        secret = password.get_secret_value() if hasattr(password, "get_secret_value") else str(password)
        return email, secret

    def _token_store_path(self) -> Path:
        raw = settings.garmin_connect_token_store or "/tmp/garminconnect_tokens"
        return Path(raw)

    def _build_api(self) -> Any:
        try:
            import garminconnect  # noqa: PLC0415
        except ImportError as exc:
            raise GarminConnectClientError(
                "garminconnect package is not installed. Add it to pyproject.toml dependencies."
            ) from exc
        email, password = self._get_credentials()
        return garminconnect.Garmin(email, password)

    def _hydrate_profile(self, api: Any) -> bool:
        """Populate api.display_name after restoring a session from disk.

        `garminconnect` sets display_name only inside login(), from
        GET /userprofile-service/socialProfile. Restoring a token with
        client.load() authenticates the session but leaves display_name None —
        and several endpoints interpolate it straight into their URL:

            get_stats            -> raises "Display name is not set"
            get_heart_rates      -> builds ".../None" and Garmin answers 403

        So a session-restored client silently loses daily stats and heart rate.
        This did not surface until the token store was moved onto a PVC: before
        that /tmp was wiped on every pod restart, so every sync did a full login
        and display_name was always set as a side effect.

        One lightweight authenticated request, and far cheaper than the login it
        replaces — login walks up to five strategies against the endpoint Garmin
        rate-limits. Returns False so the caller falls back to a full login,
        which sets display_name itself.
        """
        try:
            prof = api.client.connectapi("/userprofile-service/socialProfile")
        except Exception as exc:
            log_structured(
                logger,
                "warning",
                "Could not hydrate Garmin profile from restored session; re-authenticating",
                provider=_PROVIDER,
                error=str(exc),
            )
            return False

        if not isinstance(prof, dict) or not prof.get("displayName"):
            return False

        api.display_name = prof["displayName"]
        api.full_name = prof.get("fullName", "")
        return True

    def _try_load_saved_session(self, api: Any) -> bool:
        """Return True if we successfully loaded a saved token."""
        token_path = self._token_store_path()
        if not token_path.exists():
            return False
        try:
            api.client.load(str(token_path))
            if not api.client.is_authenticated:
                return False
            # An authenticated session is not a usable one until display_name is
            # set — see _hydrate_profile.
            if not self._hydrate_profile(api):
                return False
            log_structured(logger, "info", "Loaded saved Garmin Connect session", provider=_PROVIDER)
            return True
        except Exception as exc:
            log_structured(
                logger,
                "warning",
                "Saved Garmin Connect session is invalid, will re-authenticate",
                provider=_PROVIDER,
                error=str(exc),
            )
            return False

    def _blocked_for(self) -> int:
        """Seconds remaining before this client may talk to Garmin again (0 = free)."""
        remaining = int(self._blocked_until - time.monotonic())
        if remaining > 0:
            return remaining
        return cooldown_remaining()

    def _login(self, api: Any) -> None:
        try:
            api.login()
        except Exception as exc:
            message = str(exc)
            if _is_account_locked(message):
                cooldown = _record_rate_limit(logger)
                self._blocked_until = time.monotonic() + cooldown
                raise GarminConnectClientError(
                    f"Garmin Connect account is LOCKED — stop retrying and unlock it at "
                    f"garmin.com (password reset). Backing off {cooldown}s: {message}"
                ) from exc
            if _is_rate_limited(message):
                cooldown = _record_rate_limit(logger)
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
        log_structured(logger, "info", "Garmin Connect login successful, session saved", provider=_PROVIDER)

    def _get_api(self) -> Any:
        """Return an authenticated garminconnect.Garmin instance, logging in if necessary.

        Refuses to attempt a login while blocked: login is the rate-limited endpoint.
        """
        if self._api is not None:
            return self._api

        blocked = self._blocked_for()
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
        """Call a garminconnect method with rate-limit awareness and bounded backoff.

        Ordering matters: rate-limit is checked *before* auth, because a Cloudflare
        403 matches both and must never trigger a re-login. Genuinely transient
        errors retry with exponential backoff + jitter, honouring Retry-After.
        """
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
                    cooldown = _record_rate_limit(logger)
                    self._blocked_until = time.monotonic() + cooldown
                    raise GarminConnectRateLimitError(
                        f"Garmin Connect rate limited during {fn_name}, backing off {cooldown}s: {message}"
                    ) from exc

                if _is_auth_error(message) and not reauthed:
                    reauthed = True
                    log_structured(
                        logger,
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
                    logger,
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

    # -------------------------------------------------------------------------
    # Data access methods
    # -------------------------------------------------------------------------

    def get_activities_by_date(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """Return activity summaries between start_date and end_date (inclusive)."""
        result = self._call_with_reauth(
            "get_activities_by_date",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
        return result if isinstance(result, list) else []

    def get_sleep_data(self, cdate: date) -> dict[str, Any]:
        """Return sleep data for a single calendar date."""
        result = self._call_with_reauth("get_sleep_data", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, dict) else {}

    def get_heart_rates(self, cdate: date) -> dict[str, Any]:
        """Return heart rate data for a single calendar date."""
        result = self._call_with_reauth("get_heart_rates", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, dict) else {}

    def get_stats(self, cdate: date) -> dict[str, Any]:
        """Return daily stats (steps, calories, stress, etc.) for a calendar date."""
        result = self._call_with_reauth("get_stats", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, dict) else {}

    def get_stress_data(self, cdate: date) -> dict[str, Any]:
        """Return time-series stress data for a calendar date."""
        result = self._call_with_reauth("get_stress_data", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, dict) else {}

    def get_body_composition(self, start_date: date, end_date: date) -> dict[str, Any]:
        """Return body composition data for a date range."""
        result = self._call_with_reauth(
            "get_body_composition",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
        return result if isinstance(result, dict) else {}

    def get_max_metrics(self, cdate: date) -> list[dict[str, Any]]:
        """Return max-metrics (VO2max / fitness age) for a single calendar date.

        Garmin only writes this on days with a qualifying activity, so most
        dates return an empty list. Callers should fetch it once per sync range
        rather than per-day — see GarminConnect247Data.save_vo2max_for_range.
        """
        result = self._call_with_reauth("get_max_metrics", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, list) else []

    def get_hrv_data(self, cdate: date) -> dict[str, Any]:
        """Return HRV status data for a calendar date."""
        result = self._call_with_reauth("get_hrv_data", cdate.strftime("%Y-%m-%d"))
        return result if isinstance(result, dict) else {}

    def get_last_used_device_model(self) -> str | None:
        """Return the display name of the most recently used Garmin device.

        Cached on the instance: the strategy shares one client across the
        workouts and 24/7 handlers, so a whole sync run costs a single extra
        request rather than one per date. That distinction matters — the per-day
        loop is what got this provider IP rate-limited.

        The 24/7 endpoints do not report which device produced the data, so
        without this every 24/7 record persisted device_model=None, leaving
        device_type UNKNOWN and the UI rendering its "unknown device" fallback
        on sleep, HRV and body-metrics rows (workouts were unaffected because
        activities carry deviceName directly).
        """
        if self._device_model_cached:
            return self._device_model
        self._device_model_cached = True
        try:
            info = self._call_with_reauth("get_device_last_used")
        except Exception as exc:
            log_structured(
                logger,
                "warning",
                "Could not resolve Garmin device; 24/7 records will have no device_model",
                provider=_PROVIDER,
                error=str(exc),
            )
            return None
        if not isinstance(info, dict):
            return None
        # Garmin has used both keys across firmware/API generations.
        self._device_model = info.get("lastUsedDeviceName") or info.get("displayName") or None
        return self._device_model

    def iter_dates(self, start_date: date, end_date: date) -> list[date]:
        """Return list of calendar dates from start_date through end_date."""
        dates: list[date] = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates
