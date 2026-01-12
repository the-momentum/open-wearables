from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_64


class ProviderSetting(BaseDbModel):
    """Configuration for providers (enabled/disabled)."""

    __tablename__ = "provider_settings"

    provider: Mapped[PrimaryKey[str_64]]
    is_enabled: Mapped[bool]
