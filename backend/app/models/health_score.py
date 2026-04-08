from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDataSource, PrimaryKey, json_binary, numeric_5_2, str_10, str_32
from app.schemas.enums import HealthScoreCategory, ProviderName


class HealthScore(BaseDbModel):
    """A scored health metric (e.g. sleep score, recovery score) with optional sub-components."""

    __tablename__ = "health_score"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id",
            "category",
            "recorded_at",
            name="uq_health_score_source_category_time",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    data_source_id: Mapped[FKDataSource | None]
    provider: Mapped[ProviderName | None]

    category: Mapped[HealthScoreCategory]
    value: Mapped[numeric_5_2 | None]
    qualifier: Mapped[str_32 | None]

    recorded_at: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]

    components: Mapped[json_binary | None]
