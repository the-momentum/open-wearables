from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, OneToMany, PrimaryKey, str_10, str_100


class ExternalDeviceMapping(BaseDbModel):
    """Maps a user/provider/device combination into a reusable identifier."""

    __tablename__ = "external_device_mapping"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider_name",
            "device_id",
            name="uq_external_mapping_user_provider_device",
        ),
        Index("idx_external_mapping_user", "user_id"),
        Index("idx_external_mapping_device", "device_id"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    provider_name: Mapped[str_10]
    device_id: Mapped[str_100 | None]

    event_records: Mapped[OneToMany["EventRecord"]]
    data_points: Mapped[OneToMany["DataPointSeries"]]
