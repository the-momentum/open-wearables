from pydantic import BaseModel, Field


class ProviderSettingRead(BaseModel):
    """Provider setting with metadata."""

    provider: str = Field(..., description="Provider identifier (e.g., 'apple', 'garmin')")
    name: str = Field(..., description="Display name (e.g., 'Apple Health', 'Garmin')")
    has_cloud_api: bool = Field(..., description="Whether provider uses cloud OAuth API")
    is_enabled: bool = Field(..., description="Whether provider is enabled by admin")


class ProviderSettingUpdate(BaseModel):
    """Schema for updating provider setting."""

    is_enabled: bool


class BulkProviderSettingsUpdate(BaseModel):
    """Schema for bulk updating provider settings."""

    providers: dict[str, bool] = Field(
        ...,
        description="Map of provider_id -> is_enabled",
        examples=[{"apple": True, "garmin": True, "polar": False, "suunto": True}],
    )
