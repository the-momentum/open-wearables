from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


class InstanceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_name: str | None = None
    logo_url: str | None = None
    support_email: EmailStr | None = None
    updated_at: datetime | None = None


class InstanceSettingsUpdate(BaseModel):
    """Partial update: only the fields sent change, and an explicit null clears one."""

    organization_name: str | None = Field(None, max_length=100, description="Name shown to users of this instance")
    logo_url: HttpUrl | None = Field(None, max_length=2048, description="Absolute https URL of the logo")
    support_email: EmailStr | None = Field(None, description="Where users are told to write about problems")

    @field_validator("organization_name", mode="before")
    @classmethod
    def _blank_name_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("logo_url", "support_email", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("logo_url")
    @classmethod
    def _https_only(cls, value: HttpUrl | None) -> HttpUrl | None:
        # The logo is loaded by phones on any network; plain http would be blocked or leak the request.
        if value is not None and value.scheme != "https":
            raise ValueError("logo_url must use https")
        return value


class InstanceInfo(BaseModel):
    """Public description of this instance, read by apps before a user connects to it.

    Additive-only: apps in the stores read this from instances of many versions, so
    fields are appended, never removed or repurposed.
    """

    name: str | None = Field(description="Organisation name; null when the administrator has not set one")
    logo_url: str | None = Field(description="Absolute https URL of the organisation logo")
    support_email: str | None = Field(description="Contact address for users of this instance")
    api_version: str = Field(description="Open Wearables version running on this instance")
    app_enabled: bool = Field(
        False,
        description="Whether the Open Wearables Connect app may connect users: the instance is registered "
        "and its admin email verified",
    )
    instance_id: UUID | None = Field(
        None,
        description="Registration id at the license server (not the telemetry id); null when not registered",
    )
