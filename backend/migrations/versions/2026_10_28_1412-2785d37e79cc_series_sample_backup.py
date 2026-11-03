"""series sample backup

Revision ID: 2785d37e79cc
Revises: 6c49f0f8fba2

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2785d37e79cc"
down_revision: Union[str, None] = "6c49f0f8fba2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    "id, external_id, data_source_id, recorded_at, zone_offset, window_seconds, value, series_type_definition_id,"
    " is_daily_total, created_at"
)


def upgrade() -> None:
    op.create_table(
        "series_sample_backup",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("zone_offset", sa.String(length=10), nullable=True),
        sa.Column("window_seconds", sa.Integer(), nullable=True),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("series_type_definition_id", sa.Integer(), nullable=False),
        sa.Column("is_daily_total", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_source.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_type_definition_id"], ["series_type_definition.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_series_sample_backup_source_type_time",
        "series_sample_backup",
        ["data_source_id", "series_type_definition_id", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    # The moved values go back to series_sample, where the code before this revision reads them.
    op.execute(
        f"INSERT INTO series_sample ({_COLUMNS}) SELECT {_COLUMNS} FROM series_sample_backup ON CONFLICT DO NOTHING"
    )
    op.drop_index("ix_series_sample_backup_source_type_time", table_name="series_sample_backup")
    op.drop_table("series_sample_backup")
