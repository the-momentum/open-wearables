"""drop recovery_score series type

Recovery score is now stored in the health_score table (HealthScore model)
for all providers. The timeseries series_type_definition row (id=6) and any
remaining data_point_series rows are no longer needed.

Revision ID: drop_recovery_score_series_type
Revises: cc39513098b0

"""

from typing import Sequence, Union

from alembic import op

revision: str = "drop_recovery_score_series_type"
down_revision: Union[str, None] = "cc39513098b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM data_point_series WHERE series_type_definition_id = 6")
    op.execute("DELETE FROM data_point_series_archive WHERE series_type_definition_id = 6")
    op.execute("DELETE FROM series_type_definition WHERE id = 6")


def downgrade() -> None:
    op.execute(
        "INSERT INTO series_type_definition (id, code, unit) VALUES (6, 'recovery_score', 'score') "
        "ON CONFLICT DO NOTHING"
    )
