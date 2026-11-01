"""merge fork and upstream heads

Revision ID: 81ea20b3c94c
Revises: 19248cba05f6, 9ffc050235bd

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '81ea20b3c94c'
down_revision: Union[str, None] = ('19248cba05f6', '9ffc050235bd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
