from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, FKUserConnection, OneToMany, PrimaryKey, str_32, str_50, str_100
from app.schemas.oauth import ProviderName


class DataSource(BaseDbModel):
    """Maps a user/provider/device combination into a reusable identifier.

    user_connection_id is NULL for one-time imports (XML, manual uploads),
    populated for active connections (SDK sync, OAuth API).
    """

    __tablename__ = "data_source"
    __table_args__ = (
        Index("idx_data_source_user_provider", "user_id", "provider"),
        UniqueConstraint("user_id", "provider", "device_model", "source", name="uq_data_source_identity"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    provider: Mapped[ProviderName]
    user_connection_id: Mapped[FKUserConnection]
    device_model: Mapped[str_100 | None]
    software_version: Mapped[str_50 | None]
    source: Mapped[str_50 | None]
    device_type: Mapped[str_32 | None]
    original_source_name: Mapped[str_100 | None]

    event_records: Mapped[OneToMany["EventRecord"]]
    data_points: Mapped[OneToMany["DataPointSeries"]]
