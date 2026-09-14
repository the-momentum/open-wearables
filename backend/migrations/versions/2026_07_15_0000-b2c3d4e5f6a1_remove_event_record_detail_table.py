"""remove_event_record_detail_table

Removes the event_record_detail middle table from the joined-table polymorphic
inheritance chain. Each concrete detail table (sleep_details, workout_details,
menstrual_cycle_details) now has a direct FK to event_record.id.
detail_type is omitted — it is redundant since the Python class encodes the type.

Revision ID: b2c3d4e5f6a1
Revises: 7d6921a86914

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "7d6921a86914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old FK from each child table pointing to event_record_detail,
    #    and add a new FK pointing directly to event_record.id.
    #    record_id values are identical in both tables (joined-table inheritance
    #    shares the same PK), so no data movement is required.
    #
    #    We drop ALL foreign keys on record_id rather than naming them explicitly,
    #    because auto-generated constraint names differ across environments.
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table_name, new_fk_name in [
        ("sleep_details", "sleep_details_record_id_fkey"),
        ("workout_details", "workout_details_record_id_fkey"),
        ("menstrual_cycle_details", "menstrual_cycle_details_record_id_fkey"),
    ]:
        existing_fks = inspector.get_foreign_keys(table_name)
        fks_on_record_id = [
            fk["name"] for fk in existing_fks if fk["constrained_columns"] == ["record_id"] and fk["name"]
        ]
        with op.batch_alter_table(table_name) as batch_op:
            for fk_name in fks_on_record_id:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(
                new_fk_name,
                "event_record",
                ["record_id"],
                ["id"],
                ondelete="CASCADE",
            )

    op.drop_table("event_record_detail")

    for table_name in ("sleep_details", "workout_details", "menstrual_cycle_details"):
        op.add_column(
            table_name,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    # created_at is restored on the parent (it lived there before this migration,
    # added by 4bd01c907050) so a further downgrade through that revision finds it.
    op.create_table(
        "event_record_detail",
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("detail_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["event_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )

    for table, dtype in [
        ("sleep_details", "sleep"),
        ("workout_details", "workout"),
        ("menstrual_cycle_details", "menstrual_cycle"),
    ]:
        op.execute(
            f"INSERT INTO event_record_detail (record_id, detail_type, created_at) "
            f"SELECT record_id, '{dtype}', created_at FROM {table} ON CONFLICT (record_id) DO NOTHING"
        )

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table_name, restored_fk_name in [
        ("sleep_details", "sleep_details_record_id_fkey"),
        ("workout_details", "workout_details_record_id_fkey"),
        ("menstrual_cycle_details", "menstrual_cycle_details_record_id_fkey"),
    ]:
        existing_fks = inspector.get_foreign_keys(table_name)
        fks_on_record_id = [
            fk["name"] for fk in existing_fks if fk["constrained_columns"] == ["record_id"] and fk["name"]
        ]
        with op.batch_alter_table(table_name) as batch_op:
            for fk_name in fks_on_record_id:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(
                restored_fk_name,
                "event_record_detail",
                ["record_id"],
                ["record_id"],
                ondelete="CASCADE",
            )

    # Children never had a detail_type column before this migration (it lived only
    # on the parent), so downgrade only removes the created_at we added to them.
    for table_name in ("sleep_details", "workout_details", "menstrual_cycle_details"):
        op.drop_column(table_name, "created_at")
