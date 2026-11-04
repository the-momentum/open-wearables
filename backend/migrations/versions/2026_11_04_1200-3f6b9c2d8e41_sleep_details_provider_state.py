"""sleep details provider state

Revision ID: 3f6b9c2d8e41
Revises: e9413ac05e3b

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f6b9c2d8e41"
down_revision: Union[str, None] = "e9413ac05e3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sleep_details", sa.Column("provider_state", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("sleep_details", "provider_state")
