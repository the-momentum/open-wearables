"""align internal sleep scores to wake-up date with direct record linkage

Revision ID: a3f8c1d2e4b5
Revises: cdac07b15b04

Adds a sleep_record_id FK column to health_score so each internal sleep score
is linked directly to the event_record it was calculated from, eliminating
date-collision issues for users in extreme time zones. recorded_at is now
set to midnight of the local wake-up date (end_datetime) rather than bedtime.

Existing internal sleep scores are deleted so fill_missing_sleep_scores can
recreate them with the new linkage and correct dates.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8c1d2e4b5"
down_revision: Union[str, None] = "cdac07b15b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("health_score", sa.Column("sleep_record_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_health_score_sleep_record_id",
        "health_score",
        "event_record",
        ["sleep_record_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_health_score_sleep_record",
        "health_score",
        ["sleep_record_id"],
        unique=True,
        postgresql_where=sa.text("sleep_record_id IS NOT NULL"),
    )
    op.execute("DELETE FROM health_score WHERE provider = 'internal' AND category = 'sleep'")


def downgrade() -> None:
    # NOTE: The internal sleep-score rows deleted in upgrade() cannot be restored
    # here. fill_missing_sleep_scores will recreate them on the next run.
    op.drop_index("uq_health_score_sleep_record", table_name="health_score")
    op.drop_constraint("fk_health_score_sleep_record_id", "health_score", type_="foreignkey")
    op.drop_column("health_score", "sleep_record_id")
