"""event_record title and notes columns

Revision ID: 7ef3a1b2c4d5
Revises: cdac07b15b04

Adds the ``title`` and ``notes`` columns to ``event_record`` so that
third-party providers (Health Connect writers like Peloton, Strava,
Zwift; HealthKit writers like Peloton iOS) can preserve the
human-readable workout title and accompanying free-form notes that
the SDK sends over the wire. Both columns are nullable so existing
rows remain valid.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ef3a1b2c4d5"
down_revision: Union[str, None] = "cdac07b15b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_record",
        sa.Column("title", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "event_record",
        sa.Column("notes", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_record", "notes")
    op.drop_column("event_record", "title")
