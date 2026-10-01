"""Schemas for the data we hold per user, provider and data type."""

from datetime import datetime
from typing import NamedTuple
from uuid import UUID

from app.schemas.sync_status import DataTypeKind


class CoverageSpan(NamedTuple):
    """One data type's span within a single write, before it is merged into coverage.

    A NamedTuple rather than a BaseModel: one is built per sample on the ingest path, so
    per-instance validation would be paid millions of times for fields the caller already
    has in the right types.
    """

    user_id: UUID
    provider: str
    data_type: str
    kind: DataTypeKind
    start: datetime
    end: datetime
