"""widen_data_source_source_to_100

Revision ID: 264b79d7c541
Revises: 2d316787b998

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "264b79d7c541"
down_revision: Union[str, None] = "2d316787b998"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Apple HealthKit tags on-device sleep/records with a source bundle
    # identifier of the form "com.apple.health.<UUID>" (53 chars), which
    # overflows the old VARCHAR(50) and aborts the whole SDK import batch.
    # Widen to 100 to fit the observed reverse-DNS bundle identifiers.
    op.alter_column(
        "data_source",
        "source",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "data_source",
        "source",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
