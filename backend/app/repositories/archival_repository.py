"""Repository for archival settings and archive table operations."""

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import ColumnElement, Subquery, func, literal_column, text

from app.database import DbSession
from app.models import DataPointSeriesArchive, DataSource, SeriesSample
from app.models.archival_setting import ArchivalSetting
from app.models.series_type_definition import SeriesTypeDefinition
from app.repositories.aggregate_backfill_repository import SKIPPED_SOURCE
from app.repositories.local_day import OFFSET_REACH, every_series_type_sql, sample_day_sql, utc_midnight
from app.repositories.repositories import timeline_key_column, utc_bucket_start
from app.schemas.enums import (
    ProviderName,
    TimelineBucket,
    TimelineGroupBy,
)

# ---------------------------------------------------------------------------
# Archival Settings repository
# ---------------------------------------------------------------------------


class ArchivalSettingRepository:
    """Manages the singleton archival_settings row (id=1 enforced by check constraint)."""

    def get(self, db: DbSession) -> ArchivalSetting:
        """Return the current archival settings (singleton row with id=1)."""
        return db.query(ArchivalSetting).filter(ArchivalSetting.id == 1).one()

    def update(self, db: DbSession, rollup_enabled: bool, delete_after_days: int | None) -> ArchivalSetting:
        """Update the data lifecycle settings."""
        setting = self.get(db)
        setting.rollup_enabled = rollup_enabled
        setting.delete_after_days = delete_after_days
        db.commit()
        db.refresh(setting)
        return setting

    def mark_deleted_before(self, db: DbSession, day: date) -> None:
        """Record that samples of local days before ``day`` are gone; the mark never moves back, as a longer
        retention window does not bring deleted samples back."""
        setting = self.get(db)
        setting.deleted_before = max(setting.deleted_before or day, day)
        db.commit()


# ---------------------------------------------------------------------------
# Data-point archive repository
# ---------------------------------------------------------------------------

# Safety limits to prevent overloading the DB on initial runs
MAX_ROWS_PER_RUN = 500_000  # Stop after deleting this many rows per invocation
MAX_SECONDS_PER_RUN = 120  # Stop after this many seconds per invocation

# Sources holding a sample before the bound, in id order after a cursor: one index probe per source.
_SOURCES_WITH_SAMPLES_BEFORE = text(f"""
    SELECT ds.id FROM data_source ds
    WHERE ds.id > :after
        AND EXISTS (
            SELECT 1 FROM series_sample s
            WHERE s.data_source_id = ds.id AND {every_series_type_sql("s")} AND s.recorded_at < :before
        )
        AND NOT EXISTS (SELECT 1 FROM data_migration m WHERE m.name = :skipped || ds.id::text)
    ORDER BY ds.id LIMIT :limit
""")

# The legacy archive, read by no one since the backfill copied it; its days fall under retention like the samples.
_DELETE_ARCHIVE_BEFORE = text("""
    DELETE FROM data_point_series_archive WHERE id IN (
        SELECT a.id FROM data_point_series_archive a
        WHERE a.bucket_start_at < CAST(:cutoff AS date)
            AND NOT EXISTS (SELECT 1 FROM data_migration m WHERE m.name = :skipped || a.data_source_id::text)
        LIMIT :limit
    )
""")

# A source's earliest sample: one index probe per series type, not a scan of its history.
_EARLIEST_SAMPLE = text("""
    SELECT min(first.recorded_at) FROM series_type_definition t
    CROSS JOIN LATERAL (
        SELECT s.recorded_at FROM series_sample s
        WHERE s.data_source_id = :source_id AND s.series_type_definition_id = t.id
        ORDER BY s.recorded_at LIMIT 1
    ) first
""")


class BatchedRun(NamedTuple):
    """Rows a capped batch loop handled, and whether it got through all of them."""

    rows: int
    complete: bool


# What samples are rolled up into, and the archive they replace until it is dropped.
AGGREGATE_TABLES = frozenset({"series_aggregate", "event_record_aggregate", "data_point_series_archive"})


class DataPointSeriesArchiveRepository:
    """Handles aggregation, insertion, and deletion for the archive table."""

    def get_storage_estimate(self, db: DbSession) -> dict:
        """Get storage sizes for ALL user tables from pg_catalog.

        Returns live / aggregate / other breakdowns so the frontend can visualise
        growth projections accurately.  Also queries the actual date span of
        live data so the frontend doesn't have to guess.
        """
        result = db.execute(
            text("""
                SELECT
                    relname,
                    pg_relation_size(relid) AS data_bytes,
                    pg_indexes_size(relid) AS index_bytes,
                    pg_total_relation_size(relid) AS total_bytes,
                    n_live_tup AS row_count
                FROM pg_catalog.pg_stat_user_tables
            """)
        ).fetchall()

        live_data_bytes = 0
        live_index_bytes = 0
        live_rows = 0
        aggregate_data_bytes = 0
        aggregate_index_bytes = 0
        aggregate_rows = 0
        other_bytes = 0

        for row in result:
            if row.relname == "series_sample":
                live_data_bytes = row.data_bytes
                live_index_bytes = row.index_bytes
                live_rows = row.row_count
            elif row.relname in AGGREGATE_TABLES:
                aggregate_data_bytes += row.data_bytes
                aggregate_index_bytes += row.index_bytes
                aggregate_rows += row.row_count
            else:
                other_bytes += row.total_bytes

        # Query the actual date span of live data for accurate estimation.
        live_span_days = 0
        if live_rows > 0:
            span = db.execute(
                text("""
                    SELECT EXTRACT(DAY FROM MAX(recorded_at) - MIN(recorded_at))::int AS span
                    FROM series_sample
                """)
            ).scalar()
            live_span_days = max(span or 0, 1)

        live_total = live_data_bytes + live_index_bytes
        aggregate_total = aggregate_data_bytes + aggregate_index_bytes
        total = live_total + aggregate_total + other_bytes

        avg_live = (live_total / live_rows) if live_rows else 0.0
        avg_aggregate = (aggregate_total / aggregate_rows) if aggregate_rows else 0.0

        return {
            "live_data_bytes": live_data_bytes,
            "live_index_bytes": live_index_bytes,
            "aggregate_data_bytes": aggregate_data_bytes,
            "aggregate_index_bytes": aggregate_index_bytes,
            "other_tables_bytes": other_bytes,
            "total_bytes": total,
            "live_row_count": live_rows,
            "aggregate_row_count": aggregate_rows,
            "avg_bytes_per_live_row": round(avg_live, 1),
            "avg_bytes_per_aggregate_row": round(avg_aggregate, 1),
            "live_data_span_days": live_span_days,
            "live_total_pretty": _pretty_bytes(live_total),
            "live_data_pretty": _pretty_bytes(live_data_bytes),
            "live_index_pretty": _pretty_bytes(live_index_bytes),
            "aggregate_total_pretty": _pretty_bytes(aggregate_total),
            "aggregate_data_pretty": _pretty_bytes(aggregate_data_bytes),
            "aggregate_index_pretty": _pretty_bytes(aggregate_index_bytes),
            "other_tables_pretty": _pretty_bytes(other_bytes),
            "total_pretty": _pretty_bytes(total),
        }

    def sources_with_samples_before(self, db: DbSession, before: datetime, after: UUID, limit: int) -> list[UUID]:
        """Up to ``limit`` data sources, in id order after ``after``, holding a sample recorded before ``before``;
        never one the backfill skipped."""
        params = {"before": before, "after": after, "limit": limit, "skipped": SKIPPED_SOURCE}
        return list(db.execute(_SOURCES_WITH_SAMPLES_BEFORE, params).scalars())

    def earliest_sample(self, db: DbSession, source_id: UUID) -> datetime | None:
        return db.execute(_EARLIEST_SAMPLE, {"source_id": source_id}).scalar()

    def delete_archive_before(self, db: DbSession, cutoff_date: date, limit: int) -> int:
        """Delete up to ``limit`` rows of the legacy archive for UTC days before ``cutoff_date``; the backfill has
        copied them into the aggregate tables by the time retention runs, except a source it skipped."""
        params = {"cutoff": cutoff_date, "limit": limit, "skipped": SKIPPED_SOURCE}
        return db.execute(_DELETE_ARCHIVE_BEFORE, params).rowcount  # ty: ignore[unresolved-attribute]

    def delete_days(self, db: DbSession, source_id: UUID, days: list[date]) -> int:
        """Delete the source's samples of these consecutive local days, whole; returns the rows deleted."""
        local_day = literal_column(sample_day_sql())
        return (
            db.query(SeriesSample)
            .filter(
                SeriesSample.data_source_id == source_id,
                text(every_series_type_sql()),
                # The UTC reach of the days, so the index bounds the scan; the local day picks within it.
                SeriesSample.recorded_at >= utc_midnight(days[0]) - OFFSET_REACH,
                SeriesSample.recorded_at < utc_midnight(days[-1]) + timedelta(days=1) + OFFSET_REACH,
                local_day.in_(days),
            )
            .delete(synchronize_session=False)
        )

    def get_user_counts_by_provider_and_type_from_archive(
        self,
        db: DbSession,
        user_id: UUID,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> list[tuple[str, str, int]]:
        """Archived data point counts for a user, grouped by provider and series type.

        The counterpart of ``get_user_counts_by_provider_and_type`` on the live table, which
        once archival is enabled no longer holds anything older than the cutoff.

        Returns (provider, series_type_code, count) tuples.
        """
        days = self._deduped_archive_days(db, user_id, _archive_range_filters(start_datetime, end_datetime))
        rows = (
            db.query(DataSource.provider, SeriesTypeDefinition.code, func.sum(days.c.sample_count).label("total"))
            .select_from(days)
            .join(DataSource, days.c.data_source_id == DataSource.id)
            .join(SeriesTypeDefinition, days.c.series_type_definition_id == SeriesTypeDefinition.id)
            .group_by(DataSource.provider, SeriesTypeDefinition.code)
            .all()
        )
        return [(provider, code, int(total)) for provider, code, total in rows]

    def get_user_timeline_counts_from_archive(
        self,
        db: DbSession,
        user_id: UUID,
        bucket: TimelineBucket,
        group_by: TimelineGroupBy,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        provider: ProviderName | None = None,
    ) -> list[tuple[str, date, int]]:
        """Archived data point counts for a user, bucketed by time like the live timeline.

        Without this an archived stretch of history renders as an empty gap, which is exactly
        what the timeline exists to make visible.

        Returns (key, bucket_start, count) for non-empty buckets only.
        """
        days = self._deduped_archive_days(db, user_id, _archive_range_filters(start_datetime, end_datetime))
        bucket_start = utc_bucket_start(bucket, days.c.bucket_start_at)
        key_column = timeline_key_column(group_by)

        query = (
            db.query(key_column, bucket_start, func.sum(days.c.sample_count).label("total"))
            .select_from(days)
            .join(DataSource, days.c.data_source_id == DataSource.id)
        )
        if group_by is TimelineGroupBy.SERIES_TYPE:
            query = query.join(SeriesTypeDefinition, days.c.series_type_definition_id == SeriesTypeDefinition.id)
        if provider is not None:
            query = query.filter(DataSource.provider == provider)

        rows = query.group_by(key_column, bucket_start).order_by(key_column, bucket_start).all()
        return [(key, bucket_start_value, int(total)) for key, bucket_start_value, total in rows]

    def _deduped_archive_days(
        self,
        db: DbSession,
        user_id: UUID,
        range_filters: list[ColumnElement[bool]],
    ) -> Subquery:
        """One row per archived day of one user, so each day's samples are counted once.

        ``aggregation_type`` is part of the archive's unique key, so a day whose series type
        changed aggregation method has more than one row for the same samples.
        """
        return (
            db.query(
                DataPointSeriesArchive.data_source_id.label("data_source_id"),
                DataPointSeriesArchive.series_type_definition_id.label("series_type_definition_id"),
                DataPointSeriesArchive.bucket_start_at.label("bucket_start_at"),
                func.max(DataPointSeriesArchive.sample_count).label("sample_count"),
            )
            .join(DataSource, DataPointSeriesArchive.data_source_id == DataSource.id)
            .filter(DataSource.user_id == user_id, *range_filters)
            .group_by(
                DataPointSeriesArchive.data_source_id,
                DataPointSeriesArchive.series_type_definition_id,
                DataPointSeriesArchive.bucket_start_at,
            )
            .subquery()
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _archive_range_filters(
    start_datetime: datetime | None,
    end_datetime: datetime | None,
) -> list[ColumnElement[bool]]:
    """Range filters for archive rows, whose bucket_start_at is always a UTC midnight.

    The start is rounded down to its UTC day: an archived day is a single aggregated row
    that cannot be split, so a window opening mid-day counts that whole day rather than
    dropping it entirely.
    """
    filters: list[ColumnElement[bool]] = []
    if start_datetime is not None:
        filters.append(
            DataPointSeriesArchive.bucket_start_at
            >= _as_utc(start_datetime).replace(hour=0, minute=0, second=0, microsecond=0)
        )
    if end_datetime is not None:
        filters.append(DataPointSeriesArchive.bucket_start_at < _as_utc(end_datetime))
    return filters


def _as_utc(value: datetime) -> datetime:
    """Read a naive datetime as UTC rather than as the server's local time."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _pretty_bytes(n: int) -> str:
    """Return a human-readable byte string (e.g. '1.23 GB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.2f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # ty:ignore[invalid-assignment]
    return f"{n:.2f} PB"
