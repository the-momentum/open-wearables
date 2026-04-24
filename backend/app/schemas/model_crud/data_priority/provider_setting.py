from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import LiveSyncMode


class ProviderSettingRead(BaseModel):
    """Provider setting with metadata."""

    provider: str = Field(..., description="Provider identifier (e.g., 'apple', 'garmin')")
    name: str = Field(..., description="Display name (e.g., 'Apple Health', 'Garmin')")
    has_cloud_api: bool = Field(..., description="Whether provider uses cloud OAuth API")
    is_enabled: bool = Field(..., description="Whether provider is enabled by admin")
    icon_url: str = Field(
        ...,
        description=(
            "Relative URL to provider icon (e.g., '/static/provider-icons/garmin.svg')."
            " Resolve against the API base URL."
        ),
    )
    live_sync_mode: LiveSyncMode | None = Field(
        None,
        description="Current live sync mode ('pull' or 'webhook'). Null for SDK-only providers.",
    )
    live_sync_configurable: bool = Field(
        False,
        description="Whether the admin can switch live_sync_mode for this provider.",
    )


class ProviderSettingUpdate(BaseModel):
    """Schema for updating a single provider setting."""

    is_enabled: bool | None = None
    live_sync_mode: LiveSyncMode | None = None

    @field_validator("live_sync_mode", mode="before")
    @classmethod
    def reject_null_live_sync_mode(cls, v: object) -> object:
        if v is None:
            raise ValueError("live_sync_mode cannot be set to null; omit the field to leave it unchanged")
        return v


class BulkProviderSettingsUpdate(BaseModel):
    """Schema for bulk updating provider enabled/disabled state."""

    providers: dict[str, bool] = Field(
        ...,
        description="Map of provider_id -> is_enabled",
        examples=[{"apple": True, "garmin": True, "polar": False, "suunto": True}],
    )
