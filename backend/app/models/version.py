from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDevice, PrimaryKey, str_10, str_100


class Version(BaseDbModel):
    """A version is a specific version of a device."""

    id: Mapped[PrimaryKey[UUID]]
    device_id: Mapped[FKDevice]
    version: Mapped[str_100]
