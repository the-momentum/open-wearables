from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_64
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import DataGranularity


class ProviderSetting(BaseDbModel):
    """Per-provider configuration (one row per provider).

    Enable/disable, live sync mode, data granularity, and the OAuth app
    credentials so providers can be configured from the frontend instead of .env.
    NULL credential columns fall back to the provider's *_CLIENT_* env vars.
    """

    __tablename__ = "provider_settings"

    provider: Mapped[PrimaryKey[str_64]]
    is_enabled: Mapped[bool]
    live_sync_mode: Mapped[LiveSyncMode | None]
    data_granularity: Mapped[DataGranularity | None]

    # OAuth app credentials. client_secret/subscription_key/webhook_secret are secrets — stored encrypted.
    client_id: Mapped[str | None]
    client_secret: Mapped[str | None]
    subscription_key: Mapped[str | None]  # Suunto only
    default_scope: Mapped[str | None]
    webhook_secret: Mapped[str | None]

    # Non-secret provider-specific config that doesn't fit the columns above (e.g. Google project_id, use_reconcile).
    extra: Mapped[dict | None] = mapped_column(JSONB)
