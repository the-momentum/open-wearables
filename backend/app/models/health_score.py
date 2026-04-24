from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKDataSource, FKUser, PrimaryKey, json_binary, numeric_6_3, str_10, str_32
from app.schemas.enums import HealthScoreCategory, ProviderName


class HealthScore(BaseDbModel):
    """A scored health metric (e.g. sleep score, recovery score) with optional sub-components."""

    __tablename__ = "health_score"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            "category",
            "recorded_at",
            name="uq_health_score_user_provider_category_time",
        ),
        # SQLAlchemy's UniqueConstraint doesn't support postgresql_where, so we
        # use Index(..., unique=True) to express this partial unique constraint.
        Index(
            "uq_health_score_sleep_record",
            "sleep_record_id",
            unique=True,
            postgresql_where=text("sleep_record_id IS NOT NULL"),
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    data_source_id: Mapped[FKDataSource | None]
    provider: Mapped[ProviderName]

    category: Mapped[HealthScoreCategory]
    value: Mapped[numeric_6_3 | None]
    qualifier: Mapped[str_32 | None]

    recorded_at: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]

    components: Mapped[json_binary | None]

    sleep_record_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("event_record.id", ondelete="CASCADE"), nullable=True
    )
