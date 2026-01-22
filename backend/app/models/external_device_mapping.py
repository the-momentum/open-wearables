from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.database import BaseDbModel
from app.mappings import FKDevice, FKDeviceSoftware, FKUser, ManyToOne, OneToMany, PrimaryKey
from app.models import Device, DeviceSoftware
from app.schemas.oauth import ProviderName


class ExternalDeviceMapping(BaseDbModel):
    """Maps a user/provider/device combination into a reusable identifier."""

    __tablename__ = "external_device_mapping"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_id",
            name="uq_external_mapping_user_device",
        ),
        Index("idx_external_mapping_user", "user_id"),
        Index("idx_external_mapping_device", "device_id"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    device_id: Mapped[FKDevice]
    device_software_id: Mapped[FKDeviceSoftware]
    source: Mapped[ProviderName]

    device: Mapped[ManyToOne["Device"] | None] = relationship(
        "Device",
        foreign_keys="[ExternalDeviceMapping.device_id]",
    )
    device_software: Mapped[ManyToOne["DeviceSoftware"] | None] = relationship(
        "DeviceSoftware",
        foreign_keys="[ExternalDeviceMapping.device_software_id]",
    )

    event_records: Mapped[OneToMany["EventRecord"]]
    data_points: Mapped[OneToMany["DataPointSeries"]]
