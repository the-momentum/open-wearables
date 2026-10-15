from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import ProviderName


class SourceFilterParams(BaseModel):
    """Filters narrowing a read to one data origin, shared by every query over normalized data."""

    provider: ProviderName | None = Field(None, description="Provider filter")
    source: str | None = Field(None, description="Data source filter")
    device_model: str | None = Field(None, description="Device model filter")
    data_source_id: UUID | None = Field(None, description="Direct data source identifier filter")
