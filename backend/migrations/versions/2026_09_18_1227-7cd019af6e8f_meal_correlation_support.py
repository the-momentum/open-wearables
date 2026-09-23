"""meal correlation support

Adds a "meal" EventRecord category (e.g. HealthKit HKCorrelationType.food) plus
its meal_details table, and an optional event_record_id link on data_point_series
so nutrient samples can be grouped under the meal that contains them. Also indexes
that link (partial, non-null only) so looking up all samples for a given event
doesn't require a full table scan.

Revision ID: 7cd019af6e8f
Revises: a7c3e9f1b2d4

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7cd019af6e8f"
down_revision: Union[str, None] = "a7c3e9f1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_details",
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("meal_type", sa.String(length=32), nullable=True),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["event_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.add_column("data_point_series", sa.Column("event_record_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "data_point_series_event_record_id_fkey",
        "data_point_series",
        "event_record",
        ["event_record_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_data_point_series_event_record_id",
        "data_point_series",
        ["event_record_id"],
        unique=False,
        postgresql_where=sa.text("event_record_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_point_series_event_record_id",
        table_name="data_point_series",
        postgresql_where=sa.text("event_record_id IS NOT NULL"),
    )
    op.drop_constraint("data_point_series_event_record_id_fkey", "data_point_series", type_="foreignkey")
    op.drop_column("data_point_series", "event_record_id")
    op.drop_table("meal_details")
