"""base model created_at

Revision ID: 4bd01c907050
Revises: e4f7a2c8b390

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4bd01c907050"
down_revision: Union[str, None] = "e4f7a2c8b390"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that already have created_at (just need server_default)
TABLES_WITH_CREATED_AT = [
    "api_key",
    "application",
    "developer",
    "device_type_priority",
    "invitation",
    "provider_priority",
    "refresh_token",
    "user",
    "user_connection",
    "user_invitation_code",
]

# Tables that need the column added.
# sleep_details and workout_details are polymorphic joined-table children of
# event_record_detail; created_at lives on the parent table, not on the children.
TABLES_WITHOUT_CREATED_AT = [
    "archival_settings",
    "data_point_series",
    "data_point_series_archive",
    "data_source",
    "event_record",
    "event_record_detail",
    "health_score",
    "personal_record",
    "provider_settings",
    "series_type_definition",
]

EPOCH_SENTINEL = sa.text("'1970-01-01 00:00:00+00'")


def upgrade() -> None:
    for table in TABLES_WITHOUT_CREATED_AT:
        # Backfill existing rows with epoch sentinel, then switch default to now() for new rows.
        op.add_column(
            table,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=EPOCH_SENTINEL, nullable=False),
        )
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            existing_nullable=False,
        )

    for table in TABLES_WITH_CREATED_AT:
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table in TABLES_WITHOUT_CREATED_AT:
        op.drop_column(table, "created_at")

    for table in TABLES_WITH_CREATED_AT:
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=None,
            existing_nullable=False,
        )
