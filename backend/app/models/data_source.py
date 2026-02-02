from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, OneToMany, PrimaryKey, str_50, str_100


class DataSource(BaseDbModel):
    """Maps a user/source/device combination into a reusable identifier.

    Represents the source of health data - combines user, device model,
    software version, and data source (e.g., Apple Health SDK, Garmin Connect API).
    """

    __tablename__ = "data_source"
    __table_args__ = (
        Index("idx_data_source_user", "user_id"),
        Index("idx_data_source_user_device", "user_id", "device_model"),
        UniqueConstraint("user_id", "device_model", "source", name="uq_data_source_identity"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]

    # Device info (all optional - not all providers give this)
    device_model: Mapped[str_100 | None]  # e.g., "iPhone10,5", "Forerunner 910XT", "Suunto Vertical 2"
    software_version: Mapped[str_50 | None]  # e.g., "15.4.1", "2.48.16"
    manufacturer: Mapped[str_50 | None]  # e.g., "Apple", "Suunto", "Garmin"

    # e.g., "apple_health_sdk", "garmin_connect_api", "suunto_api"
    source: Mapped[str_50 | None]

    # Relationships
    event_records: Mapped[OneToMany["EventRecord"]]
    data_points: Mapped[OneToMany["DataPointSeries"]]
