"""health score fk rename

Revision ID: dc5ac28c4b94
Revises: b2c3d4e5f6a1

Renames health_score.sleep_record_id to event_record_id and widens its partial
unique index to (event_record_id, provider, category).

RENAME rather than autogenerate's add+drop, which would discard existing FK
values -- they're the idempotency key for fill_missing_sleep_scores.

The index gains provider and category because one score per event record was too
strict: a Polar sleep session carries both Polar's score and the internal one.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dc5ac28c4b94"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "health_score",
        "sleep_record_id",
        new_column_name="event_record_id",
        existing_type=sa.UUID(),
        existing_nullable=True,
    )
    op.execute(
        "ALTER TABLE health_score "
        "RENAME CONSTRAINT health_score_sleep_record_id_fkey TO health_score_event_record_id_fkey"
    )
    # Column set changes, so this one has to be rebuilt rather than renamed.
    op.drop_index("uq_health_score_sleep_record", table_name="health_score")
    op.create_index(
        "uq_health_score_event_record",
        "health_score",
        ["event_record_id", "provider", "category"],
        unique=True,
        postgresql_where=sa.text("event_record_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_health_score_event_record", table_name="health_score")
    op.execute(
        "ALTER TABLE health_score "
        "RENAME CONSTRAINT health_score_event_record_id_fkey TO health_score_sleep_record_id_fkey"
    )
    op.alter_column(
        "health_score",
        "event_record_id",
        new_column_name="sleep_record_id",
        existing_type=sa.UUID(),
        existing_nullable=True,
    )
    # Fails if any event record gained a second score under the wider key; resolve
    # those rows by hand rather than dropping them here.
    op.create_index(
        "uq_health_score_sleep_record",
        "health_score",
        ["sleep_record_id"],
        unique=True,
        postgresql_where=sa.text("sleep_record_id IS NOT NULL"),
    )
