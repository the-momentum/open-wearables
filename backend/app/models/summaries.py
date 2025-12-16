from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKExternalMapping, PrimaryKey, date_col, numeric_5_2, numeric_10_3


class DailyActivitySummary(BaseDbModel):
    __tablename__ = "daily_activity_summary"
    __table_args__ = (
        UniqueConstraint("external_mapping_id", "date", name="uq_daily_activity_mapping_date"),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_mapping_id: Mapped[FKExternalMapping]
    date: Mapped[date_col]

    steps: Mapped[int | None]
    distance_meters: Mapped[numeric_10_3 | None]
    floors_climbed: Mapped[int | None]
    active_calories_kcal: Mapped[numeric_10_3 | None]
    total_calories_kcal: Mapped[numeric_10_3 | None]
    active_duration_seconds: Mapped[int | None]
    sedentary_duration_seconds: Mapped[int | None]
    intensity_minutes: Mapped[dict | None] = mapped_column(JSONB)


class DailyBodySummary(BaseDbModel):
    __tablename__ = "daily_body_summary"
    __table_args__ = (
        UniqueConstraint("external_mapping_id", "date", name="uq_daily_body_mapping_date"),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_mapping_id: Mapped[FKExternalMapping]
    date: Mapped[date_col]

    weight_kg: Mapped[numeric_5_2 | None]
    body_fat_percent: Mapped[numeric_5_2 | None]
    muscle_mass_kg: Mapped[numeric_5_2 | None]
    bmi: Mapped[numeric_5_2 | None]
    resting_heart_rate_bpm: Mapped[int | None]
    avg_hrv_rmssd_ms: Mapped[numeric_5_2 | None]
    blood_pressure: Mapped[dict | None] = mapped_column(JSONB)
    basal_body_temperature_celsius: Mapped[numeric_5_2 | None]


class DailyRecoverySummary(BaseDbModel):
    __tablename__ = "daily_recovery_summary"
    __table_args__ = (
        UniqueConstraint("external_mapping_id", "date", name="uq_daily_recovery_mapping_date"),
    )

    id: Mapped[PrimaryKey[UUID]]
    external_mapping_id: Mapped[FKExternalMapping]
    date: Mapped[date_col]

    sleep_duration_seconds: Mapped[int | None]
    sleep_efficiency_percent: Mapped[numeric_5_2 | None]
    resting_heart_rate_bpm: Mapped[int | None]
    avg_hrv_rmssd_ms: Mapped[numeric_5_2 | None]
    avg_spo2_percent: Mapped[numeric_5_2 | None]
    recovery_score: Mapped[int | None]
