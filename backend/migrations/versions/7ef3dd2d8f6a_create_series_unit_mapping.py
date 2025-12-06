"""create series unit mapping table

Revision ID: 7ef3dd2d8f6a
Revises: 1f04b84d6e45
Create Date: 2025-12-05 20:20:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7ef3dd2d8f6a"
down_revision = "1f04b84d6e45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    series_type_enum = sa.Enum("steps", "heart_rate", "energy", name="seriestype")

    op.create_table(
        "series_unit_mapping",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("series_type", series_type_enum, nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_type", name="uq_series_unit_series_type"),
    )

    conn = op.get_bind()
    mapping_table = sa.table(
        "series_unit_mapping",
        sa.column("id", sa.UUID()),
        sa.column("series_type", series_type_enum),
        sa.column("unit", sa.String(length=64)),
    )
    conn.execute(
        mapping_table.insert(),
        [
            {"id": uuid4(), "series_type": "heart_rate", "unit": "bpm"},
            {"id": uuid4(), "series_type": "steps", "unit": "count"},
            {"id": uuid4(), "series_type": "energy", "unit": "kcal"},
        ],
    )


def downgrade() -> None:
    op.drop_table("series_unit_mapping")

