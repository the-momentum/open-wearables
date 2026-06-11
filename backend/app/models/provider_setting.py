from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName


class ProviderSetting(BaseDbModel):
    """Configuration for providers (enabled/disabled, live sync mode)."""

    __tablename__ = "provider_settings"

    provider: Mapped[PrimaryKey[ProviderName]]
    is_enabled: Mapped[bool]
    live_sync_mode: Mapped[LiveSyncMode | None]
    webhook_secret: Mapped[str | None]
