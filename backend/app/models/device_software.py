from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDevice, PrimaryKey, str_100


class DeviceSoftware(BaseDbModel):
    """A version is a specific version of a device."""

    __tablename__ = "device_software"

    id: Mapped[PrimaryKey[UUID]]
    device_id: Mapped[FKDevice]
    version: Mapped[str_100]
