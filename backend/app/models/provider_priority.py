"""Global provider priority configuration."""

from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz
from app.schemas.oauth import ProviderName


class ProviderPriority(BaseDbModel):
    """Global priority configuration for data providers.

    Determines which provider's data is preferred when multiple providers
    have overlapping data. Lower priority number = higher preference.

    This is a global configuration (not per-user or per-application).
    Within the same provider, device_type priority is used as secondary sort.
    """

    __tablename__ = "provider_priority"
    __table_args__ = (Index("idx_provider_priority_order", "priority"),)

    id: Mapped[PrimaryKey[UUID]]
    provider: Mapped[Unique[ProviderName]]  # Uses ProviderName enum
    priority: Mapped[int]  # 1 = highest priority
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]
