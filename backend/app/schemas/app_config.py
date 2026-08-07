from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.enums import DataGranularity
from app.utils.config_utils import AccessLogLevel, format_duration, parse_duration

RawPayloadStorage = Literal["disabled", "log", "s3"]


def _restart_required() -> Any:
    """Mark a field whose change takes effect only after a container restart."""
    return Field(json_schema_extra={"restart_required": True})


class AppConfig(BaseModel):
    """Effective runtime config: the DB value where set, otherwise the config.py default.

    Field set mirrors the app_settings columns (minus id/created_at). Built by
    ConfigService and cached in Redis (JSON snapshot) + process RAM.
    """

    model_config = ConfigDict(extra="ignore")

    # Sync behaviour
    pull_sync_lookback: timedelta | None
    historical_sync_on_connect: bool
    ingest_workout_samples: bool
    default_data_granularity: DataGranularity
    score_backfill_days: int

    # Raw payload storage (read once into the storage singleton at startup / worker_init)
    raw_payload_storage: RawPayloadStorage = _restart_required()
    raw_payload_max_size_bytes: int = _restart_required()
    store_fit_files: bool = _restart_required()

    # Sleep session tracking
    sleep_end_gap_minutes: int

    # API
    paging_limit: int

    # Email / invitations
    email_from_address: str | None
    email_from_name: str
    invitation_expire_days: int
    email_max_retries: int = _restart_required()  # baked into the send_email task decorator at import
    user_invitation_code_expire_days: int

    # Periodic task intervals (read once into the Celery beat schedule at startup)
    sync_interval_seconds: int = _restart_required()
    sleep_sync_interval_seconds: int = _restart_required()
    sleep_score_interval_seconds: int = _restart_required()
    resilience_score_interval_seconds: int = _restart_required()

    # Outgoing webhooks + access log (read once at startup: Svix client / middleware closure)
    outgoing_webhooks_enabled: bool = _restart_required()
    access_log_level: AccessLogLevel = _restart_required()
    log_error_response_body: bool = _restart_required()
    log_error_response_body_max_bytes: int = _restart_required()
    log_error_response_body_max_per_minute: int = _restart_required()

    # Data lifecycle
    archive_after_days: int | None
    delete_after_days: int | None

    @field_validator("pull_sync_lookback", mode="before")
    @classmethod
    def _parse_lookback(cls, v: object) -> object:
        # DB / Redis store the compact form ("2d"); config.py already gives a timedelta.
        return parse_duration(v) if isinstance(v, str) else v

    @field_serializer("pull_sync_lookback")
    def _dump_lookback(self, v: timedelta | None) -> str | None:
        return format_duration(v) if v is not None else None


MANAGED_SETTING_KEYS: frozenset[str] = frozenset(AppConfig.model_fields)

# Derived single source of truth: which settings need a restart, read off the field markers above.
RESTART_REQUIRED_KEYS: frozenset[str] = frozenset(
    name
    for name, field in AppConfig.model_fields.items()
    if isinstance(field.json_schema_extra, dict) and field.json_schema_extra.get("restart_required")
)


class AppConfigResponse(BaseModel):
    """Effective config plus the fields whose change needs a container restart (so the UI can warn)."""

    config: AppConfig
    restart_required_fields: list[str]


class AppConfigUpdate(BaseModel):
    """Partial update from the frontend. Only set fields are persisted (exclude_unset)."""

    model_config = ConfigDict(extra="forbid")

    pull_sync_lookback: str | None = None
    historical_sync_on_connect: bool | None = None
    ingest_workout_samples: bool | None = None
    default_data_granularity: DataGranularity | None = None
    score_backfill_days: int | None = None

    raw_payload_storage: RawPayloadStorage | None = None
    raw_payload_max_size_bytes: int | None = None
    store_fit_files: bool | None = None

    sleep_end_gap_minutes: int | None = None
    paging_limit: int | None = None

    email_from_address: str | None = None
    email_from_name: str | None = None
    invitation_expire_days: int | None = None
    email_max_retries: int | None = None
    user_invitation_code_expire_days: int | None = None

    sync_interval_seconds: int | None = None
    sleep_sync_interval_seconds: int | None = None
    sleep_score_interval_seconds: int | None = None
    resilience_score_interval_seconds: int | None = None

    outgoing_webhooks_enabled: bool | None = None
    access_log_level: AccessLogLevel | None = None
    log_error_response_body: bool | None = None
    log_error_response_body_max_bytes: int | None = None
    log_error_response_body_max_per_minute: int | None = None

    archive_after_days: int | None = Field(default=None, ge=1, le=3650)
    delete_after_days: int | None = Field(default=None, ge=1, le=7300)

    @field_validator("pull_sync_lookback")
    @classmethod
    def _validate_lookback(cls, v: str | None) -> str | None:
        if v is not None:
            parse_duration(v)  # raises ValueError on a bad format -> 422
        return v
