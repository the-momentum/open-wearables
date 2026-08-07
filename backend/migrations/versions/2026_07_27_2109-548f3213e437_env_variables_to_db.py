"""env_variables_to_db

Revision ID: 548f3213e437
Revises: b2c3d4e5f6a1

Renames archival_settings -> app_settings (preserving the singleton row) and adds
the columns for config moved out of .env, plus the provider_settings credential
columns. Backfilling existing .env values into the row is handled separately
(see ConfigService bootstrap) — this migration is schema-only.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "548f3213e437"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New app_settings columns. id / created_at / archive_after_days / delete_after_days
# already exist on the renamed archival_settings table and are preserved by the rename.
_APP_SETTINGS_NEW_COLUMNS = [
    sa.Column("pull_sync_lookback", sa.Text(), nullable=True),
    sa.Column("historical_sync_on_connect", sa.Boolean(), nullable=True),
    sa.Column("ingest_workout_samples", sa.Boolean(), nullable=True),
    sa.Column("default_data_granularity", sa.String(length=32), nullable=True),
    sa.Column("score_backfill_days", sa.Integer(), nullable=True),
    sa.Column("raw_payload_storage", sa.Text(), nullable=True),
    sa.Column("raw_payload_max_size_bytes", sa.Integer(), nullable=True),
    sa.Column("store_fit_files", sa.Boolean(), nullable=True),
    sa.Column("sleep_end_gap_minutes", sa.Integer(), nullable=True),
    sa.Column("paging_limit", sa.Integer(), nullable=True),
    sa.Column("email_from_address", sa.Text(), nullable=True),
    sa.Column("email_from_name", sa.Text(), nullable=True),
    sa.Column("invitation_expire_days", sa.Integer(), nullable=True),
    sa.Column("email_max_retries", sa.Integer(), nullable=True),
    sa.Column("user_invitation_code_expire_days", sa.Integer(), nullable=True),
    sa.Column("sync_interval_seconds", sa.Integer(), nullable=True),
    sa.Column("sleep_sync_interval_seconds", sa.Integer(), nullable=True),
    sa.Column("sleep_score_interval_seconds", sa.Integer(), nullable=True),
    sa.Column("resilience_score_interval_seconds", sa.Integer(), nullable=True),
    sa.Column("outgoing_webhooks_enabled", sa.Boolean(), nullable=True),
    sa.Column("access_log_level", sa.String(length=16), nullable=True),
    sa.Column("log_error_response_body", sa.Boolean(), nullable=True),
    sa.Column("log_error_response_body_max_bytes", sa.Integer(), nullable=True),
    sa.Column("log_error_response_body_max_per_minute", sa.Integer(), nullable=True),
]

_PROVIDER_SETTINGS_NEW_COLUMNS = [
    sa.Column("client_id", sa.Text(), nullable=True),
    sa.Column("client_secret", sa.Text(), nullable=True),
    sa.Column("subscription_key", sa.Text(), nullable=True),
    sa.Column("default_scope", sa.Text(), nullable=True),
    sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
]


def upgrade() -> None:
    # Rename (not drop+create) so the existing singleton row survives.
    op.rename_table("archival_settings", "app_settings")
    op.execute("ALTER TABLE app_settings RENAME CONSTRAINT ck_archival_settings_singleton TO ck_app_settings_singleton")
    op.execute("ALTER TABLE app_settings RENAME CONSTRAINT archival_settings_pkey TO app_settings_pkey")
    # rename_table leaves the SERIAL sequence under the old name — rename it too.
    op.execute("ALTER SEQUENCE IF EXISTS archival_settings_id_seq RENAME TO app_settings_id_seq")

    for column in _APP_SETTINGS_NEW_COLUMNS:
        op.add_column("app_settings", column)

    for column in _PROVIDER_SETTINGS_NEW_COLUMNS:
        op.add_column("provider_settings", column)


def downgrade() -> None:
    for column in _PROVIDER_SETTINGS_NEW_COLUMNS:
        op.drop_column("provider_settings", column.name)

    for column in _APP_SETTINGS_NEW_COLUMNS:
        op.drop_column("app_settings", column.name)

    op.execute("ALTER SEQUENCE IF EXISTS app_settings_id_seq RENAME TO archival_settings_id_seq")
    op.execute("ALTER TABLE app_settings RENAME CONSTRAINT app_settings_pkey TO archival_settings_pkey")
    op.execute("ALTER TABLE app_settings RENAME CONSTRAINT ck_app_settings_singleton TO ck_archival_settings_singleton")
    op.rename_table("app_settings", "archival_settings")
