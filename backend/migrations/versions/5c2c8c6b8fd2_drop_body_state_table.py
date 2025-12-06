"""drop body_state table

Revision ID: 5c2c8c6b8fd2
Revises: 7ef3dd2d8f6a
Create Date: 2025-12-05 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5c2c8c6b8fd2"
down_revision = "7ef3dd2d8f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("body_state")


def downgrade() -> None:
    op.create_table(
        "body_state",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("body_fat_percentage", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("resting_heart_rate", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

