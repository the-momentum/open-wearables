from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, FKUserConnection, OneToMany, PrimaryKey, str_32, str_50, str_100
from app.schemas.oauth import ProviderName

if TYPE_CHECKING:
    from app.models.data_point_series import DataPointSeries
    from app.models.event_record import EventRecord


class DataSource(BaseDbModel):
    """Maps a user/provider/device combination into a reusable identifier.

    user_connection_id is NULL for one-time imports (XML, manual uploads),
    populated for active connections (SDK sync, OAuth API).
    """

    __tablename__ = "data_source"
    __table_args__ = (
        Index("idx_data_source_user_provider", "user_id", "provider"),
        Index(
            "uq_data_source_identity",
            "user_id",
            "provider",
            text("COALESCE(device_model, '')"),
            text("COALESCE(source, '')"),
            unique=True,
        ),
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
