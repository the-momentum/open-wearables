"""add application table for SDK authentication

Revision ID: d7a8b9c0e1f2
Revises: 62a54b62ed20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a8b9c0e1f2"
down_revision: Union[str, None] = "62a54b62ed20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("app_secret_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("developer_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["developer_id"], ["developer.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_app_id", "application", ["app_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_application_app_id", table_name="application")
    op.drop_table("application")
