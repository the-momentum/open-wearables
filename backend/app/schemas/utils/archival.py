"""Schemas for data lifecycle / archival settings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArchivalSettingRead(BaseModel):
    """Response schema for data lifecycle settings."""

    model_config = ConfigDict(from_attributes=True)

    rollup_enabled: bool = Field(
        True,
        description="Roll changed days of samples up into daily and per-session aggregates every 15 minutes. "
        "Off, the days that change are dropped: activity and body summaries count them from the samples, day "
        "reads of sources without provider day values get no new days.",
    )
    history_rollup_enabled: bool = Field(
        False,
        description="Roll the days before up too, once, in the background. Hours on a large instance; until it is "
        "done the summaries count those days from the samples.",
    )
    delete_after_days: int | None = Field(
        None,
        description="Days before samples are deleted, rolled up first when rollup is on. NULL = kept indefinitely.",
    )


class ArchivalSettingUpdate(BaseModel):
    """Request schema for updating data lifecycle settings: a field left out keeps its saved value."""

    rollup_enabled: bool | None = Field(
        None, description="Roll samples up into daily and per-session aggregates. Left out or null: unchanged."
    )
    history_rollup_enabled: bool | None = Field(
        None,
        description="Roll the days before up too; switched on, it starts in the background. Needs rollup_enabled. "
        "Left out or null: unchanged.",
    )
    delete_after_days: int | None = Field(
        None,
        ge=1,
        le=7300,
        description="Days before samples are deleted. NULL to keep indefinitely; left out: unchanged.",
    )

    def applied_to(self, saved: ArchivalSettingRead) -> ArchivalSettingRead:
        sent = self.model_dump(exclude_unset=True)
        return saved.model_copy(
            update={field: value for field, value in sent.items() if value is not None or field == "delete_after_days"}
        )


class HistoryRollupStatus(BaseModel):
    """Where the history's rollup is. It goes through every data source twice, the last 30 days first."""

    state: Literal["off", "running", "done"]
    step: Literal["rollup_recent", "rollup_all"] | None = Field(None, description="The pass running")
    sources_done: int | None = Field(None, description="Data sources the running pass has finished")
    sources_total: int | None = Field(None, description="Data sources the pass goes through")


class StorageEstimate(BaseModel):
    """Storage sizes across all database tables."""

    live_data_bytes: int = Field(description="Data size of series_sample table (bytes)")
    live_index_bytes: int = Field(description="Index size of series_sample table (bytes)")
    aggregate_data_bytes: int = Field(description="Data size of the aggregate tables and the legacy archive (bytes)")
    aggregate_index_bytes: int = Field(description="Index size of the aggregate tables and the legacy archive (bytes)")
    other_tables_bytes: int = Field(description="Total size of all other tables (bytes)")
    total_bytes: int = Field(description="Total storage across ALL tables")
    live_row_count: int = Field(description="Number of rows in live table")
    aggregate_row_count: int = Field(description="Number of rows in the aggregate tables and the legacy archive")
    avg_bytes_per_live_row: float = Field(description="Average bytes per live row (data+index)")
    avg_bytes_per_aggregate_row: float = Field(description="Average bytes per aggregate row (data+index)")
    live_data_span_days: int = Field(description="Actual span of live data in days (MAX - MIN recorded_at)")
    live_total_pretty: str = Field(description="Human-readable live total size (data+indexes)")
    live_data_pretty: str = Field(description="Human-readable live data size")
    live_index_pretty: str = Field(description="Human-readable live index size")
    aggregate_total_pretty: str = Field(description="Human-readable aggregate total size (data+indexes)")
    aggregate_data_pretty: str = Field(description="Human-readable aggregate data size")
    aggregate_index_pretty: str = Field(description="Human-readable aggregate index size")
    other_tables_pretty: str = Field(description="Human-readable other tables size")
    total_pretty: str = Field(description="Human-readable total DB size")
    growth_class: str = Field(description="Growth complexity class: 'bounded' | 'linear_efficient' | 'linear'")


class ArchivalSettingWithEstimate(BaseModel):
    """Combined archival settings + storage estimates response."""

    settings: ArchivalSettingRead
    storage: StorageEstimate
    history_rollup: HistoryRollupStatus
