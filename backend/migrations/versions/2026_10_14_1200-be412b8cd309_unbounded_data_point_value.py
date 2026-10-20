"""unbounded data point value

Revision ID: be412b8cd309
Revises: c4e1a7b93d20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be412b8cd309"
down_revision: Union[str, None] = "c4e1a7b93d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NUMERIC(10,3) -> NUMERIC is binary compatible, so Postgres only updates the catalog
    # and does not rewrite data_point_series or its indexes.
    op.alter_column(
        "data_point_series",
        "value",
        existing_type=sa.Numeric(precision=10, scale=3),
        type_=sa.Numeric(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Rewrites the table and rounds values back to three decimal places.
    op.alter_column(
        "data_point_series",
        "value",
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=10, scale=3),
        existing_nullable=False,
    )
