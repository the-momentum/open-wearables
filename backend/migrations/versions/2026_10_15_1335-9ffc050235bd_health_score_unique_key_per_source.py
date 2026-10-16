"""health score unique key per source

Revision ID: 9ffc050235bd
Revises: b679f6226f99

Adds data_source_id to the unique key, NULLS NOT DISTINCT so provider scores (no source) stay unique
per provider. downgrade fails if two sources have a score at the same time by then.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ffc050235bd"
down_revision: Union[str, None] = "b679f6226f99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Built concurrently so writes aren't blocked, then promoted to the constraint
    with op.get_context().autocommit_block():
        # A failed earlier build leaves an invalid index behind; drop it so a retry rebuilds it
        op.drop_index(
            "uq_health_score_user_provider_source_category_time",
            table_name="health_score",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.create_index(
            "uq_health_score_user_provider_source_category_time",
            "health_score",
            ["user_id", "provider", "data_source_id", "category", "recorded_at"],
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_concurrently=True,
        )
    op.drop_constraint("uq_health_score_user_provider_category_time", "health_score", type_="unique")
    op.execute(
        "ALTER TABLE health_score ADD CONSTRAINT uq_health_score_user_provider_source_category_time "
        "UNIQUE USING INDEX uq_health_score_user_provider_source_category_time"
    )


def downgrade() -> None:
    op.drop_constraint("uq_health_score_user_provider_source_category_time", "health_score", type_="unique")
    op.create_unique_constraint(
        "uq_health_score_user_provider_category_time",
        "health_score",
        ["user_id", "provider", "category", "recorded_at"],
    )
