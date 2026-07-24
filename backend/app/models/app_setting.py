from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey
from app.schemas.enums import DataGranularity


class AppSetting(BaseDbModel):
    """Global, runtime-editable application configuration.

    Singleton table (one row, id=1). Every override column is nullable: NULL
    falls back to the .env / code default in config.py, a non-NULL value
    overrides it. Merges and replaces the former archival_settings.
    """

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]

    # Sync behaviour
    pull_sync_lookback: Mapped[str | None]  # compact duration ("2d", "20h")
    historical_sync_on_connect: Mapped[bool | None]
    ingest_workout_samples: Mapped[bool | None]
    default_data_granularity: Mapped[DataGranularity | None]
    score_backfill_days: Mapped[int | None]

    # Raw payload storage
    raw_payload_storage: Mapped[str | None]  # disabled | log | s3
    raw_payload_max_size_bytes: Mapped[int | None]
    store_fit_files: Mapped[bool | None]

    # Sleep session tracking
    sleep_end_gap_minutes: Mapped[int | None]

    # API
    paging_limit: Mapped[int | None]

    # Email / invitations (RESEND_API_KEY stays in env — secret)
    email_from_address: Mapped[str | None]
    email_from_name: Mapped[str | None]
    invitation_expire_days: Mapped[int | None]
    email_max_retries: Mapped[int | None]
    user_invitation_code_expire_days: Mapped[int | None]

    # Periodic task intervals — require a container restart to take effect (baked into Celery beat at startup).
    sync_interval_seconds: Mapped[int | None]
    sleep_sync_interval_seconds: Mapped[int | None]
    sleep_score_interval_seconds: Mapped[int | None]
    resilience_score_interval_seconds: Mapped[int | None]

    # Requires a restart for now — the Svix client is built at startup (pending a hot-reload refactor).
    outgoing_webhooks_enabled: Mapped[bool | None]

    # Data lifecycle (merged from archival_settings): NULL archive = disabled, NULL delete = keep forever.
    archive_after_days: Mapped[int | None]
    delete_after_days: Mapped[int | None]
