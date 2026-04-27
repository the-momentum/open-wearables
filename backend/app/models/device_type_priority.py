from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Indexed, Unique
from app.schemas.enums import DeviceType


class DeviceTypePriority(BaseDbModel):
    """Global priority configuration for device types.

    Within the same provider, determines which device type's data is preferred
    when multiple devices have overlapping data. Lower priority number = higher preference.

    E.g., watch data is preferred over phone data from the same provider.
    """

    __tablename__ = "device_type_priority"

    id: Mapped[PrimaryKey[UUID]]
    device_type: Mapped[Unique[DeviceType]]  # Uses DeviceType enum
    priority: Mapped[Indexed[int]]  # 1 = highest priority (watch), 99 = lowest (unknown)
    updated_at: Mapped[datetime]
