from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, PrimaryKey, str_10, str_100


class Device(BaseDbModel):
    """A device is a physical device that can be used to collect data."""

    id: Mapped[PrimaryKey[UUID]]

    serial_number: Mapped[str_100]
    provider_name: Mapped[str_10]
    name: Mapped[str_100]

    versions: Mapped[OneToMany["DeviceSoftware"]]
