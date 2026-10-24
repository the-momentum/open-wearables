"""instance settings

Revision ID: 8f27591bb5d8
Revises: 3f6b9c2d8e41

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f27591bb5d8"
down_revision: Union[str, None] = "3f6b9c2d8e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_name", sa.String(length=100), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("support_email", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_instance_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("instance_settings")
