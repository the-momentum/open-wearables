"""series types use integer ids

Revision ID: a3f2a0d6cb1a
Revises: 0cd3a6570e61
Create Date: 2025-12-05 21:45:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3f2a0d6cb1a"
down_revision = "0cd3a6570e61"
branch_labels = None
depends_on = None

SERIES_TYPES = [
    (1, "steps", "count"),
    (2, "heart_rate", "bpm"),
    (3, "energy", "kcal"),
    (4, "height", "cm"),
    (5, "weight", "kg"),
    (6, "body_fat_percentage", "percent"),
    (7, "resting_heart_rate", "bpm"),
    (8, "body_temperature", "celsius"),
    (9, "distance_walking_running", "meters"),
    (10, "distance_cycling", "meters"),
    (11, "respiratory_rate", "breaths_per_minute"),
    (12, "walking_heart_rate_average", "bpm"),
    (13, "heart_rate_variability_sdnn", "ms"),
    (14, "oxygen_saturation", "percent"),
]


def upgrade() -> None:
    op.create_table(
        "series_type_definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    conn = op.get_bind()
    conn.execute(
        sa.table(
            "series_type_definition",
            sa.column("id", sa.Integer()),
            sa.column("code", sa.String(length=64)),
            sa.column("unit", sa.String(length=64)),
        ).insert(),
        [{"id": st_id, "code": code, "unit": unit} for st_id, code, unit in SERIES_TYPES],
    )

    op.add_column("data_point_series", sa.Column("series_type_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_data_point_series_series_type",
        "data_point_series",
        "series_type_definition",
        ["series_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    for st_id, code, _ in SERIES_TYPES:
        conn.execute(
            sa.text(
                "UPDATE data_point_series SET series_type_id = :st_id WHERE series_type = :code",
            ),
            {"st_id": st_id, "code": code},
        )

    op.alter_column("data_point_series", "series_type_id", nullable=False)

    op.drop_index("idx_data_point_series_mapping_type_time", table_name="data_point_series")
    op.create_index(
        "idx_data_point_series_mapping_type_time",
        "data_point_series",
        ["external_mapping_id", "series_type_id", "recorded_at"],
    )

    op.drop_column("data_point_series", "series_type")
    op.execute("DROP TYPE IF EXISTS seriestype")

    op.drop_table("series_unit_mapping")


def downgrade() -> None:
    seriestype = sa.Enum(
        "steps",
        "heart_rate",
        "energy",
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
        name="seriestype",
    )
    seriestype.create(op.get_bind(), checkfirst=True)

    op.add_column("data_point_series", sa.Column("series_type", seriestype, nullable=True))

    conn = op.get_bind()
    for st_id, code, _ in SERIES_TYPES:
        conn.execute(
            sa.text(
                "UPDATE data_point_series SET series_type = :code WHERE series_type_id = :st_id",
            ),
            {"st_id": st_id, "code": code},
        )
    op.alter_column("data_point_series", "series_type", nullable=False)

    op.drop_index("idx_data_point_series_mapping_type_time", table_name="data_point_series")
    op.create_index(
        "idx_data_point_series_mapping_type_time",
        "data_point_series",
        ["external_mapping_id", "series_type", "recorded_at"],
    )

    op.drop_constraint("fk_data_point_series_series_type", "data_point_series", type_="foreignkey")
    op.drop_column("data_point_series", "series_type_id")

    op.create_table(
        "series_unit_mapping",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("series_type", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_type", name="uq_series_unit_series_type"),
    )
    unit_table = sa.table(
        "series_unit_mapping",
        sa.column("id", sa.UUID()),
        sa.column("series_type", sa.String(length=64)),
        sa.column("unit", sa.String(length=64)),
    )
    op.bulk_insert(
        unit_table,
        [{"id": uuid4(), "series_type": code, "unit": unit} for _, code, unit in SERIES_TYPES],
    )

    op.drop_table("series_type_definition")

