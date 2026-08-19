"""activity_summary_table

Adds the activity_summary table for Apple Health ActivitySummary ring data
(Move/Exercise/Stand values and goals). One row per data_source per day,
with UNIQUE constraint on (data_source_id, date) for idempotent upsert.

Revision ID: f1a2b3c4d5e6
Revises: b2c3d4e5f6a1

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_summary",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("active_energy_burned", sa.Numeric(10, 3), nullable=False),
        sa.Column("active_energy_burned_goal", sa.Numeric(10, 3), nullable=False),
        sa.Column("active_energy_burned_unit", sa.String(10), nullable=False),
        sa.Column("apple_move_time", sa.Numeric(10, 3), nullable=False),
        sa.Column("apple_move_time_goal", sa.Numeric(10, 3), nullable=False),
        sa.Column("apple_exercise_time", sa.Numeric(10, 3), nullable=False),
        sa.Column("apple_exercise_time_goal", sa.Numeric(10, 3), nullable=False),
        sa.Column("apple_stand_hours", sa.Numeric(10, 3), nullable=False),
        sa.Column("apple_stand_hours_goal", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_source.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("data_source_id", "date", name="uq_activity_summary_source_date"),
    )


def downgrade() -> None:
    op.drop_table("activity_summary")
