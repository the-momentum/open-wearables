"""add steps_total to workout details

Revision ID: 1f04b84d6e45
Revises: 6a859c59b5de
Create Date: 2025-12-05 20:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f04b84d6e45"
down_revision = "6a859c59b5de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workout_details",
        sa.Column("steps_total", sa.Numeric(precision=10, scale=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workout_details", "steps_total")

