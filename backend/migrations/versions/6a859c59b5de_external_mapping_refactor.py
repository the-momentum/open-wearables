"""external mapping refactor

Revision ID: 6a859c59b5de
Revises: fbbab7b4040b
Create Date: 2025-12-05 18:29:00.000000
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a859c59b5de"
down_revision: str | None = "fbbab7b4040b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


event_fk_name = "event_record_user_id_fkey"
event_mapping_fk = "fk_event_record_external_mapping"
series_mapping_fk = "fk_data_point_series_external_mapping"


def _ensure_mapping(
    bind,
    mapping_table,
    cache,
    user_id,
    provider_id,
    device_id,
):
    if user_id is None:
        return None

    identity = (str(user_id), provider_id, device_id)
    if identity in cache:
        return cache[identity]

    mapping_id = uuid4()
    bind.execute(
        mapping_table.insert().values(
            id=mapping_id,
            user_id=user_id,
            provider_id=provider_id,
            device_id=device_id,
        ),
    )
    cache[identity] = mapping_id
    return mapping_id


def upgrade() -> None:
    op.create_table(
        "external_device_mapping",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=True),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider_id",
            "device_id",
            name="uq_external_mapping_user_provider_device",
        ),
    )
    op.create_index("idx_external_mapping_user", "external_device_mapping", ["user_id"])
    op.create_index("idx_external_mapping_device", "external_device_mapping", ["device_id"])

    op.drop_index("idx_event_record_time", table_name="event_record")
    op.drop_index("idx_event_record_user_category", table_name="event_record")
    op.drop_index("idx_data_point_series_device_type_time", table_name="data_point_series")

    op.add_column("event_record", sa.Column("external_mapping_id", sa.UUID(), nullable=True))
    op.add_column("data_point_series", sa.Column("external_mapping_id", sa.UUID(), nullable=True))

    op.create_foreign_key(
        event_mapping_fk,
        "event_record",
        "external_device_mapping",
        ["external_mapping_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        series_mapping_fk,
        "data_point_series",
        "external_device_mapping",
        ["external_mapping_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=("external_device_mapping", "event_record", "data_point_series"))

    mapping_table = sa.Table("external_device_mapping", metadata, autoload_with=bind)
    event_table = sa.Table("event_record", metadata, autoload_with=bind)
    data_point_table = sa.Table("data_point_series", metadata, autoload_with=bind)

    mapping_cache: dict[tuple[str, str | None, str | None], UUID] = {}

    event_rows = bind.execute(
        sa.select(
            event_table.c.id,
            event_table.c.user_id,
            event_table.c.provider_id,
            event_table.c.device_id,
        ),
    ).fetchall()

    for row in event_rows:
        mapping_id = _ensure_mapping(
            bind,
            mapping_table,
            mapping_cache,
            row.user_id,
            row.provider_id,
            row.device_id,
        )
        if mapping_id:
            bind.execute(
                event_table.update()
                .where(event_table.c.id == row.id)
                .values(external_mapping_id=mapping_id),
            )

    data_point_has_user = "user_id" in data_point_table.c
    data_point_has_provider = "provider_id" in data_point_table.c

    if data_point_has_user:
        data_rows = bind.execute(
            sa.select(
                data_point_table.c.id,
                data_point_table.c.user_id,
                data_point_table.c.provider_id if data_point_has_provider else sa.literal(None),
                data_point_table.c.device_id if "device_id" in data_point_table.c else sa.literal(None),
            ),
        ).fetchall()

        for row in data_rows:
            mapping_id = _ensure_mapping(
                bind,
                mapping_table,
                mapping_cache,
                row.user_id,
                row.provider_id if data_point_has_provider else None,
                row.device_id,
            )
            if mapping_id:
                bind.execute(
                    data_point_table.update()
                    .where(data_point_table.c.id == row.id)
                    .values(external_mapping_id=mapping_id),
                )
    else:
        # Without the user_id column present we cannot backfill existing rows reliably.
        bind.execute(sa.delete(data_point_table))

    op.alter_column("event_record", "external_mapping_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("data_point_series", "external_mapping_id", existing_type=sa.UUID(), nullable=False)

    op.drop_constraint(event_fk_name, "event_record", type_="foreignkey")
    op.drop_column("event_record", "user_id")
    op.drop_column("event_record", "provider_id")
    op.drop_column("event_record", "device_id")

    if "user_id" in data_point_table.c:
        op.drop_column("data_point_series", "user_id")
    if "provider_id" in data_point_table.c:
        op.drop_column("data_point_series", "provider_id")
    if "device_id" in data_point_table.c:
        op.drop_column("data_point_series", "device_id")

    op.create_index(
        "idx_event_record_mapping_category",
        "event_record",
        ["external_mapping_id", "category"],
    )
    op.create_index(
        "idx_event_record_mapping_time",
        "event_record",
        ["external_mapping_id", "start_datetime", "end_datetime"],
    )
    op.create_index(
        "idx_data_point_series_mapping_type_time",
        "data_point_series",
        ["external_mapping_id", "series_type", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_data_point_series_mapping_type_time", table_name="data_point_series")
    op.drop_index("idx_event_record_mapping_time", table_name="event_record")
    op.drop_index("idx_event_record_mapping_category", table_name="event_record")

    op.add_column("event_record", sa.Column("device_id", sa.String(length=100), nullable=True))
    op.add_column("event_record", sa.Column("provider_id", sa.String(length=100), nullable=True))
    op.add_column("event_record", sa.Column("user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(event_fk_name, "event_record", "user", ["user_id"], ["id"], ondelete="CASCADE")

    op.add_column("data_point_series", sa.Column("device_id", sa.String(length=100), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=("external_device_mapping", "event_record", "data_point_series"))

    mapping_table = sa.Table("external_device_mapping", metadata, autoload_with=bind)
    event_table = sa.Table("event_record", metadata, autoload_with=bind)
    data_point_table = sa.Table("data_point_series", metadata, autoload_with=bind)

    event_rows = bind.execute(
        sa.select(
            event_table.c.id,
            event_table.c.external_mapping_id,
        ),
    ).fetchall()

    for row in event_rows:
        mapping = bind.execute(
            sa.select(mapping_table.c.user_id, mapping_table.c.provider_id, mapping_table.c.device_id).where(
                mapping_table.c.id == row.external_mapping_id,
            ),
        ).one_or_none()
        if not mapping:
            continue
        bind.execute(
            event_table.update()
            .where(event_table.c.id == row.id)
            .values(
                user_id=mapping.user_id,
                provider_id=mapping.provider_id,
                device_id=mapping.device_id,
            ),
        )

    data_rows = bind.execute(
        sa.select(
            data_point_table.c.id,
            data_point_table.c.external_mapping_id,
        ),
    ).fetchall()

    for row in data_rows:
        mapping = bind.execute(
            sa.select(mapping_table.c.device_id).where(mapping_table.c.id == row.external_mapping_id),
        ).one_or_none()
        bind.execute(
            data_point_table.update()
            .where(data_point_table.c.id == row.id)
            .values(device_id=mapping.device_id if mapping else None),
        )

    op.alter_column("event_record", "user_id", existing_type=sa.UUID(), nullable=False)

    op.drop_constraint(series_mapping_fk, "data_point_series", type_="foreignkey")
    op.drop_constraint(event_mapping_fk, "event_record", type_="foreignkey")

    op.drop_column("data_point_series", "external_mapping_id")
    op.drop_column("event_record", "external_mapping_id")

    op.create_index("idx_data_point_series_device_type_time", "data_point_series", ["device_id", "series_type", "recorded_at"])
    op.create_index("idx_event_record_user_category", "event_record", ["user_id", "category"])
    op.create_index("idx_event_record_time", "event_record", ["user_id", "start_datetime", "end_datetime"])

    op.drop_index("idx_external_mapping_device", table_name="external_device_mapping")
    op.drop_index("idx_external_mapping_user", table_name="external_device_mapping")
    op.drop_table("external_device_mapping")

