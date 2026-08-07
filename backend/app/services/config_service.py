import time
from datetime import timedelta
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.config import _raw_settings as settings  # raw pydantic Settings, not the proxy
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.repositories.app_settings_repository import AppSettingRepository
from app.schemas.app_config import MANAGED_SETTING_KEYS, AppConfig, AppConfigUpdate
from app.utils.config_utils import format_duration

# access_log_level is derived from ENVIRONMENT at runtime, not a real env customization —
# leave it NULL so the fallback (settings.access_log_level) keeps deriving it.
_BACKFILL_SKIP = frozenset({"access_log_level"})

_REDIS_HASH = "app:config"
_DATA_FIELD = "data"
_VERSION_FIELD = "version"
_MICRO_TTL_SECONDS = 5.0


def _to_column(value: Any) -> Any:
    # DB stores pull_sync_lookback as a compact duration string; everything else stores as-is.
    if isinstance(value, timedelta):
        return format_duration(value)
    return value


# ── Redis I/O — one function per operation, so it's obvious what touches Redis and how ──


def _redis_read_version() -> int | None:
    """Cheap poll (single HGET): the current config version, or None if the hash is cold."""
    raw = get_redis_client().hget(_REDIS_HASH, _VERSION_FIELD)
    return int(raw) if raw is not None else None


def _redis_read_snapshot() -> tuple[str | bytes | None, int | None]:
    """Read data + version together (one HGETALL) so a reader never pairs mismatched values."""
    snap = get_redis_client().hgetall(_REDIS_HASH)
    raw_version = snap.get(_VERSION_FIELD)
    return snap.get(_DATA_FIELD), (int(raw_version) if raw_version is not None else None)


def _redis_publish(config: AppConfig) -> int:
    """Atomically store the snapshot and bump the version; returns the new version."""
    pipe = get_redis_client().pipeline()
    pipe.hset(_REDIS_HASH, _DATA_FIELD, config.model_dump_json())
    pipe.hincrby(_REDIS_HASH, _VERSION_FIELD, 1)
    return pipe.execute()[1]


def _redis_seed(config: AppConfig) -> None:
    """Seed a cold hash from the DB source of truth without clobbering a concurrent writer."""
    pipe = get_redis_client().pipeline()
    pipe.hsetnx(_REDIS_HASH, _DATA_FIELD, config.model_dump_json())
    pipe.hsetnx(_REDIS_HASH, _VERSION_FIELD, 0)
    pipe.execute()


class ConfigService:
    """Effective config resolved as DB-value-else-config.py-default, cached in Redis + RAM.

    Reads hit process RAM (nanoseconds). At most once per _MICRO_TTL — and only when a read
    actually happens — a process polls the shared Redis version; only when it changed does it
    refetch the snapshot. Writes bump the version so every process picks the change up without a
    restart. If Redis is unavailable, reads keep serving the last in-RAM snapshot instead of failing.
    """

    def __init__(self) -> None:
        self._repo = AppSettingRepository()
        self._cache: AppConfig | None = None
        self._seen_version: int = -1
        self._checked_at: float = 0.0

    def clear_cache(self) -> None:
        """Drop the in-process snapshot so the next get() reloads. Used by tests between cases."""
        self._cache = None
        self._seen_version = -1
        self._checked_at = 0.0

    def get(self) -> AppConfig:
        now = time.monotonic()
        if self._cache is not None and now - self._checked_at < _MICRO_TTL_SECONDS:
            return self._cache

        try:
            version = _redis_read_version()
            if version is not None and version == self._seen_version and self._cache is not None:
                self._checked_at = now
                return self._cache
            config, version = self._load_snapshot()
            self._cache, self._seen_version, self._checked_at = config, version, now
            return config
        except (RedisError, SQLAlchemyError):
            return self._degraded(now)

    def _degraded(self, now: float) -> AppConfig:
        """Infra hiccup — resolve in priority order: last-known RAM snapshot → DB → code defaults.

        RAM first so a Redis blip never reverts a customized value; the DB (source of truth) before
        code defaults so a fresh process during a Redis blip still gets the real values; code defaults
        only when nothing is reachable (e.g. importing/tests without infra — pre-DB behaviour).
        """
        if self._cache is not None:
            self._checked_at = now
            return self._cache
        try:
            config = self._reload_from_db()
        except SQLAlchemyError:
            config = self._config_from_settings()
        self._cache, self._checked_at = config, now
        return config

    def update(self, update: AppConfigUpdate) -> AppConfig:
        fields = update.model_dump(exclude_unset=True)
        if not fields:
            # Nothing to change — don't bump the version or force every process to reload.
            return self.get()

        with SessionLocal() as db:
            row = self._repo.get(db)
            for key, value in fields.items():
                setattr(row, key, value)
            self._repo.update(db, row)

        config = self._reload_from_db()
        version = _redis_publish(config)
        self._cache, self._seen_version, self._checked_at = config, version, time.monotonic()
        return config

    def backfill_from_env(self) -> None:
        """One-time copy of customized .env values into NULL columns (idempotent).

        Only fills columns that are still NULL and whose env value differs from the
        config.py default, so untouched settings keep tracking the code default and
        admin-set values are never overwritten.
        """
        settings_fields = type(settings).model_fields
        with SessionLocal() as db:
            row = self._repo.get(db)
            changed = False
            for key in MANAGED_SETTING_KEYS:
                if key in _BACKFILL_SKIP or getattr(row, key) is not None:
                    continue
                if key not in settings_fields:  # e.g. archive/delete_after_days have no env source
                    continue
                value = getattr(settings, key)
                if value == settings_fields[key].default:
                    continue
                setattr(row, key, _to_column(value))
                changed = True
            if changed:
                db.commit()

    def _load_snapshot(self) -> tuple[AppConfig, int]:
        """(Re)load the shared snapshot, seeding a cold Redis from the DB source of truth first."""
        data, version = _redis_read_snapshot()
        if data is None or version is None:
            config = self._reload_from_db()
            _redis_seed(config)
            data, version = _redis_read_snapshot()
            if data is None:  # flushed again mid-seed (extremely unlikely) — use what we just built
                return config, version or 0
        return AppConfig.model_validate_json(data), version or 0

    def _reload_from_db(self) -> AppConfig:
        with SessionLocal() as db:
            row = self._repo.get(db)
        effective = {
            key: (getattr(row, key) if getattr(row, key) is not None else getattr(settings, key, None))
            for key in MANAGED_SETTING_KEYS
        }
        return AppConfig.model_validate(effective)

    def _config_from_settings(self) -> AppConfig:
        """Static fallback (no DB/Redis): effective config from env/code defaults only."""
        effective = {key: getattr(settings, key, None) for key in MANAGED_SETTING_KEYS}
        return AppConfig.model_validate(effective)


config_service = ConfigService()


def get_config() -> AppConfig:
    """Effective app config (cached). Use in place of reading these values off `settings`."""
    return config_service.get()
