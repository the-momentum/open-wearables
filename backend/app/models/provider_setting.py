from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName


class ProviderSetting(BaseDbModel):
    """Configuration for providers (enabled/disabled, live sync mode)."""

    __tablename__ = "provider_settings"

    # Explicit String(64): the column predates the ProviderName entry in
    # type_annotation_map, which maps to String(50).
    provider: Mapped[ProviderName] = mapped_column(String(64), primary_key=True)
    is_enabled: Mapped[bool]
    live_sync_mode: Mapped[LiveSyncMode | None]
    webhook_secret: Mapped[str | None]
