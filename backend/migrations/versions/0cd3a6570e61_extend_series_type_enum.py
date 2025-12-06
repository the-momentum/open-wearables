"""extend series type enum with biometric metrics

Revision ID: 0cd3a6570e61
Revises: 5c2c8c6b8fd2
Create Date: 2025-12-05 21:00:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy import column, table, text


# revision identifiers, used by Alembic.
revision = "0cd3a6570e61"
down_revision = "5c2c8c6b8fd2"
branch_labels = None
depends_on = None


NEW_SERIES_TYPES = [
    "height",
    "weight",
    "body_fat_percentage",
    "resting_heart_rate",
    "body_temperature",
    "distance_walking_running",
    "distance_cycling",
    "respiratory_rate",
    "walking_heart_rate_average",
    "heart_rate_variability_sdnn",
    "oxygen_saturation",
]

SERIES_UNITS = {
    "height": "cm",
    "weight": "kg",
    "body_fat_percentage": "percent",
    "resting_heart_rate": "bpm",
    "body_temperature": "celsius",
    "distance_walking_running": "meters",
    "distance_cycling": "meters",
    "respiratory_rate": "breaths_per_minute",
    "walking_heart_rate_average": "bpm",
    "heart_rate_variability_sdnn": "ms",
    "oxygen_saturation": "percent",
}


def upgrade() -> None:
    for value in NEW_SERIES_TYPES:
        op.execute(text(f"ALTER TYPE seriestype ADD VALUE '{value}'"))

    mapping_table = table(
        "series_unit_mapping",
        column("id", sa.UUID()),
        column("series_type", sa.String(length=64)),
        column("unit", sa.String(length=64)),
    )
    op.bulk_insert(
        mapping_table,
        [
            {"id": uuid4(), "series_type": series_type, "unit": SERIES_UNITS[series_type]}
            for series_type in NEW_SERIES_TYPES
        ],
    )


def downgrade() -> None:
    # Removing values from a PostgreSQL ENUM is non-trivial; instead we recreate the type.
    # 1. Rename existing type
    op.execute("ALTER TYPE seriestype RENAME TO seriestype_old")

    # 2. Create the new (reduced) type
    op.execute(
        "CREATE TYPE seriestype AS ENUM ('steps', 'heart_rate', 'energy')"
    )

    # 3. Alter columns that used the old type
    op.execute("ALTER TABLE data_point_series ALTER COLUMN series_type TYPE seriestype USING series_type::text::seriestype")
    op.execute("ALTER TABLE series_unit_mapping ALTER COLUMN series_type TYPE seriestype USING series_type::text::seriestype")

    # 4. Drop the old type
    op.execute("DROP TYPE seriestype_old")

    # 5. Remove rows for the dropped series types from mapping table
    op.execute(
        "DELETE FROM series_unit_mapping WHERE series_type NOT IN ('steps', 'heart_rate', 'energy')"
    )

