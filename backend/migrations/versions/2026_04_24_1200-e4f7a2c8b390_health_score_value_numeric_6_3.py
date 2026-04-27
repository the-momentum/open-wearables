"""health_score value precision increase to NUMERIC(6,3)

Revision ID: e4f7a2c8b390
Revises: 1f0831f5831e

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f7a2c8b390"
down_revision: Union[str, None] = "1f0831f5831e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "health_score",
        "value",
        existing_type=sa.Numeric(precision=5, scale=2),
        type_=sa.Numeric(precision=6, scale=3),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "health_score",
        "value",
        existing_type=sa.Numeric(precision=6, scale=3),
        type_=sa.Numeric(precision=5, scale=2),
        existing_nullable=True,
    )
