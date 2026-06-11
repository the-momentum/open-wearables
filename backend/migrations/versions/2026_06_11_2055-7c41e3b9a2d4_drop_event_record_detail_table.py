"""drop event_record_detail table

Revision ID: 7c41e3b9a2d4
Revises: d8a0bc9afdd9

The event_record_detail table duplicated record_id 1:1 with its child tables
and carried only the detail_type discriminator and created_at. The detail
models now use concrete inheritance: each child table references event_record
directly and the discriminator is implied by the table itself.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c41e3b9a2d4"
down_revision: Union[str, None] = "d8a0bc9afdd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DETAIL_TABLES = {
    "workout_details": "workout",
    "sleep_details": "sleep",
    "menstrual_cycle_details": "menstrual_cycle",
}


def upgrade() -> None:
    for table in DETAIL_TABLES:
        # New rows default to now(); existing rows are then backfilled with the
        # timestamp preserved on the base table before it is dropped.
        op.add_column(
            table,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.execute(
            f"UPDATE {table} AS child SET created_at = base.created_at "
            f"FROM event_record_detail AS base WHERE base.record_id = child.record_id"
        )
        op.drop_constraint(f"{table}_record_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_record_id_fkey",
            table,
            "event_record",
            ["record_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_table("event_record_detail")


def downgrade() -> None:
    op.create_table(
        "event_record_detail",
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("detail_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["event_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )

    for table, detail_type in DETAIL_TABLES.items():
        op.execute(
            f"INSERT INTO event_record_detail (record_id, detail_type, created_at) "
            f"SELECT record_id, '{detail_type}', created_at FROM {table}"
        )
        op.drop_constraint(f"{table}_record_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_record_id_fkey",
            table,
            "event_record_detail",
            ["record_id"],
            ["record_id"],
            ondelete="CASCADE",
        )
        op.drop_column(table, "created_at")
