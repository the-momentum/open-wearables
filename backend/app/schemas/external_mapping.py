from uuid import UUID

from pydantic import BaseModel


class ExternalMappingBase(BaseModel):
    """Shared fields for mapping external provider/device identifiers."""

    user_id: UUID
    provider_id: str | None = None
    device_id: str | None = None


class ExternalMappingCreate(ExternalMappingBase):
    """Payload used when persisting a new mapping."""

    id: UUID


class ExternalMappingUpdate(ExternalMappingBase):
    """Payload used when adjusting an existing mapping."""


class ExternalMappingResponse(ExternalMappingBase):
    """Representation returned via APIs."""

    id: UUID

