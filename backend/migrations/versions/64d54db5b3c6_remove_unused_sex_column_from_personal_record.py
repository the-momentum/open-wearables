"""remove_unused_sex_column_from_personal_record

Revision ID: 64d54db5b3c6
Revises: 62a54b62ed20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64d54db5b3c6"
down_revision: Union[str, None] = "62a54b62ed20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("personal_record", "sex")


def downgrade() -> None:
    op.add_column(
        "personal_record",
        sa.Column("sex", sa.Boolean(), nullable=True),
    )
