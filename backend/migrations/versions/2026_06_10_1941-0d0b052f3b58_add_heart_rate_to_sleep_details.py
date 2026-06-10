"""add_heart_rate_to_sleep_details

Revision ID: 0d0b052f3b58
Revises: d8a0bc9afdd9

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d0b052f3b58"
down_revision: Union[str, None] = "d8a0bc9afdd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sleep_details", sa.Column("heart_rate_min", sa.Integer(), nullable=True))
    op.add_column("sleep_details", sa.Column("heart_rate_avg", sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("sleep_details", "heart_rate_avg")
    op.drop_column("sleep_details", "heart_rate_min")
