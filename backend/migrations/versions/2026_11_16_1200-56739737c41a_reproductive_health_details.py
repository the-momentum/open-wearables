"""reproductive health details

Revision ID: 56739737c41a
Revises: 3f6b9c2d8e41

Reproductive health entries from the mobile SDKs are event records keyed by their
external id, like meals: a flow and a mucus entry of one day share their interval.
The two partial unique indexes on event_record switch from `meal` alone to both categories.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "56739737c41a"
down_revision: Union[str, None] = "3f6b9c2d8e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KEYED = "category IN ('meal', 'reproductive_health')"
_TIME_KEYED = "category NOT IN ('meal', 'reproductive_health')"


def upgrade() -> None:
    op.create_table(
        "reproductive_health_details",
        sa.Column("value", sa.String(length=32), nullable=True),
        sa.Column("cycle_start", sa.Boolean(), nullable=True),
        sa.Column("protection_used", sa.Boolean(), nullable=True),
        sa.Column("cervical_mucus_sensation", sa.String(length=32), nullable=True),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["event_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )

    with op.get_context().autocommit_block():
        op.create_index(
            "ix_event_record_source_external_id",
            "event_record",
            ["data_source_id", "external_id"],
            unique=True,
            postgresql_where=sa.text(_KEYED),
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_event_record_meal_source_external_id", table_name="event_record", postgresql_concurrently=True
        )
        op.create_index(
            "ix_event_record_source_time_tmp",
            "event_record",
            ["data_source_id", "start_datetime", "end_datetime"],
            unique=True,
            postgresql_where=sa.text(_TIME_KEYED),
            postgresql_concurrently=True,
        )
        op.drop_index("ix_event_record_source_time", table_name="event_record", postgresql_concurrently=True)
        op.execute("ALTER INDEX ix_event_record_source_time_tmp RENAME TO ix_event_record_source_time")


def downgrade() -> None:
    # The older time index would reject entries that share an interval, so they go first.
    op.execute("DELETE FROM event_record WHERE category = 'reproductive_health'")
    op.execute("DELETE FROM data_type_coverage WHERE data_type = 'reproductive_health'")
    op.drop_table("reproductive_health_details")

    with op.get_context().autocommit_block():
        op.create_index(
            "ix_event_record_source_time_tmp",
            "event_record",
            ["data_source_id", "start_datetime", "end_datetime"],
            unique=True,
            postgresql_where=sa.text("category <> 'meal'"),
            postgresql_concurrently=True,
        )
        op.drop_index("ix_event_record_source_time", table_name="event_record", postgresql_concurrently=True)
        op.execute("ALTER INDEX ix_event_record_source_time_tmp RENAME TO ix_event_record_source_time")
        op.create_index(
            "ix_event_record_meal_source_external_id",
            "event_record",
            ["data_source_id", "external_id"],
            unique=True,
            postgresql_where=sa.text("category = 'meal'"),
            postgresql_concurrently=True,
        )
        op.drop_index("ix_event_record_source_external_id", table_name="event_record", postgresql_concurrently=True)
