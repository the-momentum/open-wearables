"""align enum column types with type_annotation_map

Revision ID: b242cc23cb56
Revises: d8a0bc9afdd9

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b242cc23cb56"
down_revision: Union[str, None] = "d8a0bc9afdd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEVICETYPE_LABELS = ("WATCH", "BAND", "PHONE", "SCALE", "RING", "OTHER", "UNKNOWN")


def upgrade() -> None:
    # ProviderName maps to String(50) in type_annotation_map; these two
    # columns predate that entry and were created as VARCHAR(64). The longest
    # provider name is 10 chars, so shrinking is safe.
    op.alter_column(
        "user_connection",
        "provider",
        existing_type=sa.String(length=64),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "provider_settings",
        "provider",
        existing_type=sa.String(length=64),
        type_=sa.String(length=50),
        existing_nullable=False,
    )

    # Replace the native devicetype enum with VARCHAR(32) so DeviceType can
    # live in type_annotation_map like the other enums. The native enum
    # stored member names ("WATCH") while data_source.device_type stores
    # StrEnum values ("watch"), which also broke the device-type priority
    # join in data_point_series_repository - lowercase while converting.
    op.alter_column(
        "device_type_priority",
        "device_type",
        existing_type=sa.Enum(*DEVICETYPE_LABELS, name="devicetype"),
        type_=sa.String(length=32),
        postgresql_using="lower(device_type::text)",
        existing_nullable=False,
    )
    op.execute("DROP TYPE devicetype")


def downgrade() -> None:
    devicetype = sa.Enum(*DEVICETYPE_LABELS, name="devicetype")
    devicetype.create(op.get_bind())
    op.alter_column(
        "device_type_priority",
        "device_type",
        existing_type=sa.String(length=32),
        type_=devicetype,
        postgresql_using="upper(device_type)::devicetype",
        existing_nullable=False,
    )

    op.alter_column(
        "provider_settings",
        "provider",
        existing_type=sa.String(length=50),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "user_connection",
        "provider",
        existing_type=sa.String(length=50),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
