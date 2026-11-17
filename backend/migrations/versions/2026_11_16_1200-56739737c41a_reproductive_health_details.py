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
_TIME_COLUMNS = ["data_source_id", "start_datetime", "end_datetime"]
_EXTERNAL_ID_COLUMNS = ["data_source_id", "external_id"]
_TIME = "ix_event_record_source_time"
_TIME_TMP = "ix_event_record_source_time_tmp"
_KEYED_EXTERNAL_ID = "ix_event_record_source_external_id"
_MEAL_EXTERNAL_ID = "ix_event_record_meal_source_external_id"

# Each step below may already be done: the table commits before the concurrent index builds,
# so a retry after a failed build starts over with whatever the first attempt left behind.


def _drop_index(name: str) -> None:
    op.drop_index(name, table_name="event_record", postgresql_concurrently=True, if_exists=True)


def _build_index(name: str, columns: list[str], where: str) -> None:
    # A failed concurrent build leaves an invalid index behind, which IF NOT EXISTS would keep.
    invalid = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE c.relname = :name AND NOT i.indisvalid"
        ),
        {"name": name},
    )
    if invalid.first():
        _drop_index(name)
    op.create_index(
        name,
        "event_record",
        columns,
        unique=True,
        postgresql_where=sa.text(where),
        postgresql_concurrently=True,
        if_not_exists=True,
    )


def _replace_time_index(where: str) -> None:
    _build_index(_TIME_TMP, _TIME_COLUMNS, where)
    _drop_index(_TIME)
    op.execute(f"ALTER INDEX {_TIME_TMP} RENAME TO {_TIME}")


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
        if_not_exists=True,
    )

    with op.get_context().autocommit_block():
        _build_index(_KEYED_EXTERNAL_ID, _EXTERNAL_ID_COLUMNS, _KEYED)
        _drop_index(_MEAL_EXTERNAL_ID)
        _replace_time_index(_TIME_KEYED)


def downgrade() -> None:
    # The older time index would reject entries that share an interval, so they go first.
    op.execute("DELETE FROM event_record WHERE category = 'reproductive_health'")
    op.execute("DELETE FROM data_type_coverage WHERE data_type = 'reproductive_health'")
    op.drop_table("reproductive_health_details", if_exists=True)

    with op.get_context().autocommit_block():
        _replace_time_index("category <> 'meal'")
        _build_index(_MEAL_EXTERNAL_ID, _EXTERNAL_ID_COLUMNS, "category = 'meal'")
        _drop_index(_KEYED_EXTERNAL_ID)
