from uuid import UUID

from pydantic import BaseModel

from app.schemas.oauth import ProviderName


class ExternalMappingBase(BaseModel):
    """Shared fields for mapping external provider/device identifiers."""

    user_id: UUID
    device_id: UUID | None
    device_software_id: UUID | None = None
    source: ProviderName


class ExternalMappingCreate(ExternalMappingBase):
    """Payload used when persisting a new mapping."""

    id: UUID


class ExternalMappingUpdate(ExternalMappingBase):
    """Payload used when adjusting an existing mapping."""


class ExternalMappingResponse(ExternalMappingBase):
    """Representation returned via APIs."""

    id: UUID
