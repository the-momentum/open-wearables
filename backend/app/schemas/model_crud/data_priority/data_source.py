from uuid import UUID

from app.schemas.oauth import ProviderName
from pydantic import BaseModel


class DataSourceBase(BaseModel):
    user_id: UUID
    provider: ProviderName
    user_connection_id: UUID | None = None
    device_model: str | None = None
    software_version: str | None = None
    source: str | None = None
    device_type: str | None = None
    original_source_name: str | None = None


class DataSourceCreate(DataSourceBase):
    id: UUID


class DataSourceUpdate(BaseModel):
    provider: ProviderName | None = None
    user_connection_id: UUID | None = None
    device_model: str | None = None
    software_version: str | None = None
    source: str | None = None
    device_type: str | None = None
    original_source_name: str | None = None


class DataSourceResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider: ProviderName
    user_connection_id: UUID | None = None
    device_model: str | None = None
    software_version: str | None = None
    source: str | None = None
    device_type: str | None = None
    original_source_name: str | None = None
    display_name: str | None = None

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    items: list[DataSourceResponse]
    total: int
