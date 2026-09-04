from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName

# Allowlist for user sort columns - keep in sync with Literal type below
USER_SORT_COLUMNS: frozenset[str] = frozenset(
    {"created_at", "email", "first_name", "last_name", "name", "last_synced_at"}
)


class UserInclude(StrEnum):
    """Optional expansions for user read models, requested via the `include` query parameter."""

    CONNECTIONS = "connections"


_EXTERNAL_USER_ID_DEPRECATION = (
    "Deprecated: no data-fetching endpoint (timeseries, workouts, sleep, summaries, health-scores, etc.) "
    "accepts external_user_id - they all require the Open Wearables UUID. This field was added early in the "
    "project but never wired into those endpoints, so it only works as a filter on GET /users. Store the "
    "UUID returned by POST /users in your own system instead."
)


class UserQueryParams(BaseModel):
    """Query parameters for filtering and searching users.

    Args:
        page: The page number (1-based).
        limit: The number of results per page.
        sort_by: The field to sort by.
        sort_order: The sort order.
        search: The search term.
        email: Filter by exact email match.
        external_user_id: Filter by external user ID.
        provider: Filter by connected provider.
        connection_status: Narrow the provider filter to a single connection status.
        has_active_connection: Filter by presence of at least one active connection.
        last_synced_before: Filter by absence of recent syncs.
        include: Optional expansions to embed in each user.
    """

    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(20, ge=1, le=100, description="Number of results per page")

    sort_by: Literal["created_at", "email", "first_name", "last_name", "name", "last_synced_at"] | None = Field(
        "created_at",
        description="Field to sort by. 'name' orders by first name, then last name, with unnamed users last",
    )
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order")

    search: str | None = Field(
        None,
        description=(
            "Search across first_name, last_name, and email (partial match). "
            "A term that is a valid UUID also matches that user's id exactly"
        ),
    )

    email: EmailStr | None = Field(None, description="Filter by exact email")
    external_user_id: str | None = Field(
        None,
        description=f"Filter by external user ID. {_EXTERNAL_USER_ID_DEPRECATION}",
        deprecated=True,
    )

    provider: list[ProviderName] | None = Field(
        None,
        description=(
            "Filter by connected provider; repeat the parameter to match any of several. "
            "Matches connections in any status unless connection_status is also given"
        ),
    )
    connection_status: ConnectionStatus | None = Field(
        None,
        description="Narrow the provider filter to connections in this status",
    )
    has_active_connection: bool | None = Field(
        None,
        description=(
            "True: users with at least one active connection. "
            "False: users with none, including those who never connected a provider"
        ),
    )
    last_synced_before: datetime | None = Field(
        None,
        description=(
            "Users whose connections have all been idle since this timestamp, including those that never synced"
        ),
    )

    include: list[UserInclude] = Field(
        default_factory=list,
        description="Optional expansions to embed in each user; repeat the parameter for several",
    )


class UserConnectionSummary(BaseModel):
    """Compact per-provider connection state, embedded in user list rows."""

    provider: str
    status: ConnectionStatus
    last_synced_at: datetime | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    external_user_id: str | None = Field(None, description=_EXTERNAL_USER_ID_DEPRECATION, deprecated=True)
    last_synced_at: datetime | None = None
    last_synced_provider: str | None = Field(
        None, description="Provider that synced most recently, or null if none of them ever synced"
    )
    has_active_connection: bool = Field(
        False, description="Whether any connection is active. Mirrors the has_active_connection filter"
    )
    connections: list[UserConnectionSummary] | None = Field(
        None,
        description="Connections of every status. Present only when requested via `include=connections`",
    )


class UserCreate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = Field(None, description=_EXTERNAL_USER_ID_DEPRECATION, deprecated=True)


class UserCreateInternal(UserCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = Field(None, description=_EXTERNAL_USER_ID_DEPRECATION, deprecated=True)


class UserUpdateInternal(UserUpdate):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
