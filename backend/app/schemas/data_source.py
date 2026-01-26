from uuid import UUID

from pydantic import BaseModel


class DataSourceBase(BaseModel):
    """Shared fields for data source mappings."""

    user_id: UUID
    device_model: str | None = None
    software_version: str | None = None
    manufacturer: str | None = None
    source: str | None = None


class DataSourceCreate(DataSourceBase):
    """Payload used when persisting a new data source."""

    id: UUID


class DataSourceUpdate(BaseModel):
    """Payload used when adjusting an existing data source."""

    device_model: str | None = None
    software_version: str | None = None
    manufacturer: str | None = None
    source: str | None = None


class DataSourceResponse(DataSourceBase):
    """Representation returned via APIs."""

    id: UUID
