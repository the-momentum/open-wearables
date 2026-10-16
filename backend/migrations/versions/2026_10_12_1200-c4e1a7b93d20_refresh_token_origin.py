"""refresh_token_origin

Replace refresh_token.app_id, which mixed application app_ids with "admin:{developer_id}" and
"invite:{developer_id}" strings, with an explicit origin plus real foreign keys to application
and developer.

SDK refresh tokens whose application no longer exists are deleted: they were never cut off when
the application was removed, and from now on deleting an application cascades to its tokens.

Revision ID: c4e1a7b93d20
Revises: 4b9d28928ca1

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e1a7b93d20"
down_revision: Union[str, None] = "4b9d28928ca1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORIGIN_CHECK = (
    "(token_type = 'sdk' AND ("
    "(origin = 'application' AND application_id IS NOT NULL AND issued_by_developer_id IS NULL)"
    " OR (origin IN ('admin', 'invite') AND application_id IS NULL)))"
    " OR (token_type = 'developer' AND origin IS NULL"
    " AND application_id IS NULL AND issued_by_developer_id IS NULL)"
)


def upgrade() -> None:
    op.add_column("refresh_token", sa.Column("origin", sa.String(length=32), nullable=True))
    op.add_column("refresh_token", sa.Column("application_id", sa.UUID(), nullable=True))
    op.add_column("refresh_token", sa.Column("issued_by_developer_id", sa.UUID(), nullable=True))

    op.execute(
        """
        UPDATE refresh_token rt
        SET origin = 'application', application_id = a.id
        FROM application a
        WHERE rt.token_type = 'sdk' AND rt.app_id = a.app_id
        """
    )
    # admin:/invite: tokens keep working even if the issuing developer is gone (issuer becomes NULL)
    op.execute(
        """
        UPDATE refresh_token
        SET origin = split_part(app_id, ':', 1)
        WHERE token_type = 'sdk' AND origin IS NULL AND split_part(app_id, ':', 1) IN ('admin', 'invite')
        """
    )
    op.execute(
        """
        UPDATE refresh_token rt
        SET issued_by_developer_id = d.id
        FROM developer d
        WHERE rt.origin IN ('admin', 'invite') AND d.id::text = split_part(rt.app_id, ':', 2)
        """
    )
    # Anything left points at an application that was deleted
    op.execute("DELETE FROM refresh_token WHERE token_type = 'sdk' AND origin IS NULL")

    op.drop_column("refresh_token", "app_id")
    op.create_foreign_key(
        "refresh_token_application_id_fkey",
        "refresh_token",
        "application",
        ["application_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "refresh_token_issued_by_developer_id_fkey",
        "refresh_token",
        "developer",
        ["issued_by_developer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_refresh_token_application_id"), "refresh_token", ["application_id"], unique=False)
    op.create_check_constraint("ck_refresh_token_origin", "refresh_token", ORIGIN_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_refresh_token_origin", "refresh_token", type_="check")
    op.drop_index(op.f("ix_refresh_token_application_id"), table_name="refresh_token")
    op.drop_constraint("refresh_token_issued_by_developer_id_fkey", "refresh_token", type_="foreignkey")
    op.drop_constraint("refresh_token_application_id_fkey", "refresh_token", type_="foreignkey")
    op.add_column("refresh_token", sa.Column("app_id", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE refresh_token rt
        SET app_id = a.app_id
        FROM application a
        WHERE rt.origin = 'application' AND rt.application_id = a.id
        """
    )
    op.execute(
        """
        UPDATE refresh_token
        SET app_id = origin || ':' || coalesce(issued_by_developer_id::text, '')
        WHERE origin IN ('admin', 'invite')
        """
    )

    op.drop_column("refresh_token", "issued_by_developer_id")
    op.drop_column("refresh_token", "application_id")
    op.drop_column("refresh_token", "origin")
