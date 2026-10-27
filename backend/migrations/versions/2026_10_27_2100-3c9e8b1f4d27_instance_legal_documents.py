"""instance legal documents

Revision ID: 3c9e8b1f4d27
Revises: 7a2ed21c443a

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c9e8b1f4d27"
down_revision: Union[str, None] = "7a2ed21c443a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("privacy_policy_url", sa.Text(), nullable=True))
    op.add_column("instance_settings", sa.Column("terms_url", sa.Text(), nullable=True))
    op.add_column(
        "instance_settings",
        sa.Column("require_acceptance", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "instance_settings",
        sa.Column("legal_documents_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_table(
        "legal_acceptance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("documents_version", sa.Integer(), nullable=False),
        sa.Column("privacy_policy_url", sa.Text(), nullable=True),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "documents_version", name="uq_legal_acceptance_user_version"),
    )


def downgrade() -> None:
    op.drop_table("legal_acceptance")
    op.drop_column("instance_settings", "legal_documents_version")
    op.drop_column("instance_settings", "require_acceptance")
    op.drop_column("instance_settings", "terms_url")
    op.drop_column("instance_settings", "privacy_policy_url")
