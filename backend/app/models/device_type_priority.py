"""Global device type priority configuration."""

from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz
from app.schemas.device_type import DeviceType


class DeviceTypePriority(BaseDbModel):
    """Global priority configuration for device types.

    Within the same provider, determines which device type's data is preferred
    when multiple devices have overlapping data. Lower priority number = higher preference.

    E.g., watch data is preferred over phone data from the same provider.
    """

    __tablename__ = "device_type_priority"
    __table_args__ = (Index("idx_device_type_priority_order", "priority"),)

    id: Mapped[PrimaryKey[UUID]]
    device_type: Mapped[Unique[DeviceType]]  # Uses DeviceType enum
    priority: Mapped[int]  # 1 = highest priority (watch), 99 = lowest (unknown)
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]
