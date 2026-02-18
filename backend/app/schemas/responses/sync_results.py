from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ProviderSyncResult(BaseModel):
    success: bool
    params: dict[str, Any]


class SyncVendorDataResult(BaseModel):
    user_id: UUID | str
    start_date: str | None = None
    end_date: str | None = None
    providers_synced: dict[str, ProviderSyncResult] = {}
    errors: dict[str, str] = {}
    message: str | None = None


class SyncAllUsersResult(BaseModel):
    users_for_sync: int
