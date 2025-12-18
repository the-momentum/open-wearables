"""add invitation table and developer name fields

Revision ID: c1a2b3c4d5e6
Revises: 62a54b62ed20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3c4d5e6"
down_revision: Union[str, None] = "62a54b62ed20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add first_name and last_name to developer table
    op.add_column("developer", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("developer", sa.Column("last_name", sa.String(length=100), nullable=True))

    # Create invitation table
    op.create_table(
        "invitation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_id"], ["developer.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitation_token", "invitation", ["token"], unique=True)
    op.create_index("ix_invitation_email_status", "invitation", ["email", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invitation_email_status", table_name="invitation")
    op.drop_index("ix_invitation_token", table_name="invitation")
    op.drop_table("invitation")

    # Remove first_name and last_name from developer table
    op.drop_column("developer", "last_name")
    op.drop_column("developer", "first_name")
