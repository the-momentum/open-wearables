from pydantic import BaseModel, Field

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


class BulkProviderSettingsUpdate(BaseModel):
    """Schema for bulk updating provider enabled/disabled state."""

    providers: dict[str, bool] = Field(
        ...,
        description="Map of provider_id -> is_enabled",
        examples=[{"apple": True, "garmin": True, "polar": False, "suunto": True}],
    )
