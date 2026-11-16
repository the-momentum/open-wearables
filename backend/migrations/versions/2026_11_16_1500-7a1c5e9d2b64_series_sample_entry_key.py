"""series_sample entry key

Revision ID: 7a1c5e9d2b64
Revises: 3f6b9c2d8e41
Create Date: 2026-11-16 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a1c5e9d2b64"
down_revision: Union[str, None] = "3f6b9c2d8e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "uq_series_sample_source_type_time"
_NEW = "uq_series_sample_source_type_time_entry"
_OLD_COLUMNS = ["data_source_id", "series_type_definition_id", "recorded_at"]


def upgrade() -> None:
    op.add_column("series_sample", sa.Column("entry_key", sa.String(100), nullable=True))
    # Stored rows all have a NULL entry key, and NULLS NOT DISTINCT keeps them unique per source, type and instant
    op.create_unique_constraint(_NEW, "series_sample", [*_OLD_COLUMNS, "entry_key"], postgresql_nulls_not_distinct=True)
    op.drop_constraint(_OLD, "series_sample", type_="unique")


def downgrade() -> None:
    # Items that share an instant can't fit the old key, so only the one with the lowest id stays
    op.execute("""
        DELETE FROM series_sample s
        USING (
            SELECT r.id, row_number() OVER (
                PARTITION BY r.data_source_id, r.series_type_definition_id, r.recorded_at ORDER BY r.id
            ) AS position
            FROM series_sample r
            WHERE (r.data_source_id, r.series_type_definition_id, r.recorded_at) IN (
                SELECT data_source_id, series_type_definition_id, recorded_at
                FROM series_sample WHERE entry_key IS NOT NULL
            )
        ) ranked
        WHERE s.id = ranked.id AND ranked.position > 1
    """)
    op.create_unique_constraint(_OLD, "series_sample", _OLD_COLUMNS)
    op.drop_constraint(_NEW, "series_sample", type_="unique")
    op.drop_column("series_sample", "entry_key")
