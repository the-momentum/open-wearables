from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_64
from app.schemas.auth import LiveSyncMode


class ProviderSetting(BaseDbModel):
    """Configuration for providers (enabled/disabled, live sync mode)."""

    __tablename__ = "provider_settings"

    provider: Mapped[PrimaryKey[str_64]]
    is_enabled: Mapped[bool]
    live_sync_mode: Mapped[LiveSyncMode | None]
