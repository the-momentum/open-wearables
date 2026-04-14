from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Indexed, Unique
from app.schemas.enums import ProviderName


class ProviderPriority(BaseDbModel):
    """Global priority configuration for data providers.

    Determines which provider's data is preferred when multiple providers
    have overlapping data. Lower priority number = higher preference.

    This is a global configuration (not per-user or per-application).
    Within the same provider, device_type priority is used as secondary sort.
    """

    __tablename__ = "provider_priority"

    id: Mapped[PrimaryKey[UUID]]
    provider: Mapped[Unique[ProviderName]]  # Uses ProviderName enum
    priority: Mapped[Indexed[int]]  # 1 = highest priority
    updated_at: Mapped[datetime]
