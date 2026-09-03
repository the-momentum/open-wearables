"""Add durable whole-run manifests for streaming SDK uploads.

Revision ID: a91c3f7e2b10
Revises: dc5ac28c4b94
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a91c3f7e2b10"
down_revision: Union[str, None] = "dc5ac28c4b94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sdk_sync_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("client_sync_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_chunks", sa.Integer(), nullable=True),
        sa.Column("received_chunks", sa.Integer(), nullable=False),
        sa.Column("processed_chunks", sa.Integer(), nullable=False),
        sa.Column("received_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("received_sleep_items", sa.Integer(), nullable=False),
        sa.Column("declared_total_items", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", "client_sync_id", name="uq_sdk_sync_run_client"),
    )
    op.create_index("ix_sdk_sync_run_user_id", "sdk_sync_run", ["user_id"])
    op.create_index("ix_sdk_sync_run_status_updated", "sdk_sync_run", ["status", "updated_at"])
    op.create_table(
        "sdk_sync_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id"),
        sa.UniqueConstraint("run_id", "chunk_index", name="uq_sdk_sync_chunk_index"),
    )
    op.create_index("ix_sdk_sync_chunk_run_id", "sdk_sync_chunk", ["run_id"])
    op.create_index("ix_sdk_sync_chunk_run_status", "sdk_sync_chunk", ["run_id", "status"])


def downgrade() -> None:
    op.drop_table("sdk_sync_chunk")
    op.drop_table("sdk_sync_run")
