"""Store Apple Health menstrual-flow intensity and cycle-start marker.

Revision ID: f1b9d8c2e460
Revises: 9ffc050235bd
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1b9d8c2e460"
down_revision: Union[str, None] = "9ffc050235bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("menstrual_cycle_details", sa.Column("flow_intensity", sa.String(length=32), nullable=True))
    op.add_column("menstrual_cycle_details", sa.Column("is_cycle_start", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("menstrual_cycle_details", "is_cycle_start")
    op.drop_column("menstrual_cycle_details", "flow_intensity")
