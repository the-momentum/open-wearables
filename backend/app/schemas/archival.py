"""Schemas for data lifecycle / archival settings."""

from pydantic import BaseModel, ConfigDict, Field


class ArchivalSettingRead(BaseModel):
    """Response schema for archival settings."""

    model_config = ConfigDict(from_attributes=True)

    archive_after_days: int | None = Field(
        None,
        description="Days before live samples are aggregated into daily archive. NULL = archival disabled.",
    )
    delete_after_days: int | None = Field(
        None,
        description="Days before archived data is permanently removed. NULL = kept indefinitely.",
    )


class ArchivalSettingUpdate(BaseModel):
    """Request schema for updating archival settings."""

    archive_after_days: int | None = Field(
        None,
        ge=1,
        le=3650,
        description="Days before live data is archived. NULL to disable archival.",
    )
    delete_after_days: int | None = Field(
        None,
        ge=1,
        le=7300,
        description="Days before data is permanently deleted. NULL to keep indefinitely.",
    )


class StorageEstimate(BaseModel):
    """Storage sizes across all database tables."""

    live_data_bytes: int = Field(description="Data size of data_point_series table (bytes)")
    live_index_bytes: int = Field(description="Index size of data_point_series table (bytes)")
    archive_data_bytes: int = Field(description="Data size of archive table (bytes)")
    archive_index_bytes: int = Field(description="Index size of archive table (bytes)")
    other_tables_bytes: int = Field(description="Total size of all other tables (bytes)")
    total_bytes: int = Field(description="Total storage across ALL tables")
    live_row_count: int = Field(description="Number of rows in live table")
    archive_row_count: int = Field(description="Number of rows in archive table")
    avg_bytes_per_live_row: float = Field(description="Average bytes per live row (data+index)")
    avg_bytes_per_archive_row: float = Field(description="Average bytes per archive row (data+index)")
    live_data_span_days: int = Field(description="Actual span of live data in days (MAX - MIN recorded_at)")
    live_total_pretty: str = Field(description="Human-readable live total size (data+indexes)")
    live_data_pretty: str = Field(description="Human-readable live data size")
    live_index_pretty: str = Field(description="Human-readable live index size")
    archive_total_pretty: str = Field(description="Human-readable archive total size (data+indexes)")
    archive_data_pretty: str = Field(description="Human-readable archive data size")
    archive_index_pretty: str = Field(description="Human-readable archive index size")
    other_tables_pretty: str = Field(description="Human-readable other tables size")
    total_pretty: str = Field(description="Human-readable total DB size")
    growth_class: str = Field(description="Growth complexity class: 'bounded' | 'linear_efficient' | 'linear'")


class ArchivalSettingWithEstimate(BaseModel):
    """Combined archival settings + storage estimates response."""

    settings: ArchivalSettingRead
    storage: StorageEstimate
