"""distinguish Polar nightly aggregates from samples"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8d41c2f0a617"
down_revision: Union[str, None] = "2e31d06a8c7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_point_series",
        sa.Column("sample_role", sa.String(length=100), server_default="measurement", nullable=False),
    )
    op.execute(
        sa.text(
            """
            UPDATE data_point_series AS point
            SET sample_role = 'nightly_aggregate'
            FROM data_source AS point_source
            WHERE point_source.id = point.data_source_id
              AND point_source.provider = 'polar'
              AND point.series_type_definition_id IN (7, 24)
              AND (point.recorded_at AT TIME ZONE 'UTC')::time = TIME '00:00:00'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_point_series AS point
            SET sample_role = 'nightly_sample'
            FROM data_source AS point_source
            WHERE point_source.id = point.data_source_id
              AND point_source.provider = 'polar'
              AND point.series_type_definition_id IN (7, 24)
              AND point.sample_role = 'measurement'
              AND EXISTS (
                  SELECT 1
                  FROM event_record AS sleep
                  JOIN data_source AS sleep_source ON sleep_source.id = sleep.data_source_id
                  WHERE sleep.category = 'sleep'
                    AND sleep_source.user_id = point_source.user_id
                    AND sleep_source.provider = 'polar'
                    AND point.recorded_at BETWEEN sleep.start_datetime AND sleep.end_datetime
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("data_point_series", "sample_role")
