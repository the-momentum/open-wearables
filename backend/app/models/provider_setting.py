from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_64
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import DataGranularity


class ProviderSetting(BaseDbModel):
    """Configuration for providers (enabled/disabled, live sync mode, data granularity)."""

    __tablename__ = "provider_settings"

    provider: Mapped[PrimaryKey[str_64]]
    is_enabled: Mapped[bool]
    live_sync_mode: Mapped[LiveSyncMode | None]
    webhook_secret: Mapped[str | None]
    data_granularity: Mapped[DataGranularity | None]
