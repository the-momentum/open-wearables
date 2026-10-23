"""Repository for archival settings and archive table operations."""

import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from itertools import batched
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import ColumnElement, Date, Subquery, and_, case, cast, func, literal_column, text

from app.database import DbSession
from app.models import DataPointSeriesArchive, DataSource, SeriesSample
from app.models.archival_setting import ArchivalSetting
from app.models.series_type_definition import SeriesTypeDefinition
from app.repositories.local_day import OFFSET_REACH, sample_day_sql, utc_midnight
from app.repositories.repositories import timeline_key_column, utc_bucket_start
from app.schemas.enums import (
    ProviderName,
    SeriesType,
    TimelineBucket,
    TimelineGroupBy,
    get_series_type_id,
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
# Local days deleted per statement and commit: three days of 1 Hz data is a quarter million rows.
DELETE_DAYS_PER_BATCH = 3


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

    def delete_live_before(
        self,
        db: DbSession,
        cutoff_date: date,
        before_delete: Callable[[DbSession, UUID], None] | None = None,
    ) -> BatchedRun:
        """Permanently delete live rows of local days before *cutoff_date*, a few data sources at a time.

        A local day goes whole, so a rollup run on what is left never sees a day cut short.
        ``before_delete`` runs for each data source first, in the same transaction (the rollup).
        Stops after MAX_ROWS_PER_RUN rows or MAX_SECONDS_PER_RUN seconds; the next run continues.

        Returns the number of live rows deleted, and whether none older are left.
        """
        total_deleted = 0
        start_time = time.monotonic()
        hi = utc_midnight(cutoff_date) + OFFSET_REACH
        local_day = literal_column(sample_day_sql())
        older = and_(SeriesSample.recorded_at < hi, local_day < cutoff_date)

        def out_of_budget() -> bool:
            return total_deleted >= MAX_ROWS_PER_RUN or time.monotonic() - start_time >= MAX_SECONDS_PER_RUN

        while True:
            if out_of_budget():
                return BatchedRun(total_deleted, complete=False)

            source_ids = [row[0] for row in db.query(SeriesSample.data_source_id).filter(older).distinct().limit(10)]
            if not source_ids:
                return BatchedRun(total_deleted, complete=True)

            for source_id in source_ids:
                if before_delete is not None:
                    before_delete(db, source_id)
                    db.commit()
                # Whole local days go in each batch: a day left half-deleted would roll up as half a day.
                days = [
                    row[0]
                    for row in db.query(local_day)
                    .filter(SeriesSample.data_source_id == source_id, older)
                    .distinct()
                    .order_by(local_day)
                ]
                for batch in batched(days, DELETE_DAYS_PER_BATCH):
                    total_deleted += (
                        db.query(SeriesSample)
                        .filter(SeriesSample.data_source_id == source_id, older, local_day.in_(batch))
                        .delete(synchronize_session=False)
                    )
                    db.commit()
                    if out_of_budget():
                        return BatchedRun(total_deleted, complete=False)

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

    def get_daily_activity_aggregates_from_archive(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        series_type_ids: list[int],
    ) -> list[dict]:
        """Query the archive table for daily activity aggregates.

        Returns dicts compatible with the live-table activity aggregate format
        so the summaries service can merge both result sets.
        """
        steps_id = get_series_type_id(SeriesType.steps)
        energy_id = get_series_type_id(SeriesType.active_energy)
        basal_energy_id = get_series_type_id(SeriesType.basal_energy)
        total_energy_id = get_series_type_id(SeriesType.total_energy)
        hr_id = get_series_type_id(SeriesType.heart_rate)
        distance_id = get_series_type_id(SeriesType.distance_walking_running)
        flights_id = get_series_type_id(SeriesType.flights_climbed)
        active_time_id = get_series_type_id(SeriesType.active_time)

        # Ensure we filter using UTC datetime range
        start_ts = start_date
        if isinstance(start_ts, date) and not isinstance(start_ts, datetime):
            start_ts = datetime.combine(start_ts, datetime.min.time(), tzinfo=timezone.utc)
        elif isinstance(start_ts, datetime) and start_ts.tzinfo is None:
            start_ts = start_ts.replace(tzinfo=timezone.utc)

        end_ts = end_date
        if isinstance(end_ts, date) and not isinstance(end_ts, datetime):
            end_ts = datetime.combine(end_ts, datetime.min.time(), tzinfo=timezone.utc)
        if isinstance(end_ts, datetime) and end_ts.tzinfo is None:
            end_ts = end_ts.replace(tzinfo=timezone.utc)

        results = (
            db.query(
                cast(DataPointSeriesArchive.bucket_start_at, Date).label("activity_date"),
                DataSource.provider.label("provider"),
                DataSource.source.label("source"),
                DataSource.device_model.label("device_model"),
                DataSource.device_type.label("device_type"),
                func.sum(
                    case(
                        (DataPointSeriesArchive.series_type_definition_id == steps_id, DataPointSeriesArchive.value),
                    )
                ).label("steps_sum"),
                func.sum(
                    case(
                        (DataPointSeriesArchive.series_type_definition_id == energy_id, DataPointSeriesArchive.value),
                    )
                ).label("active_energy_sum"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == basal_energy_id,
                            DataPointSeriesArchive.value,
                        ),
                    )
                ).label("basal_energy_sum"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == total_energy_id,
                            DataPointSeriesArchive.value,
                        ),
                    )
                ).label("total_energy_sum"),
                func.avg(
                    case(
                        (DataPointSeriesArchive.series_type_definition_id == hr_id, DataPointSeriesArchive.value),
                        else_=None,
                    )
                ).label("hr_avg"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == distance_id,
                            DataPointSeriesArchive.value,
                        ),
                    )
                ).label("distance_sum"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == flights_id,
                            DataPointSeriesArchive.value,
                        ),
                    )
                ).label("flights_climbed_sum"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == active_time_id,
                            DataPointSeriesArchive.value,
                        ),
                    )
                ).label("active_time_sum"),
            )
            .join(DataSource, DataPointSeriesArchive.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                DataPointSeriesArchive.bucket_start_at >= start_ts,
                DataPointSeriesArchive.bucket_start_at < end_ts,
                DataPointSeriesArchive.series_type_definition_id.in_(series_type_ids),
            )
            .group_by(
                cast(DataPointSeriesArchive.bucket_start_at, Date),
                DataSource.provider,
                DataSource.source,
                DataSource.device_model,
                DataSource.device_type,
            )
            .all()
        )

        aggregates = []
        for row in results:
            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "provider": row.provider,
                    "source": row.source,
                    "device_model": row.device_model,
                    "device_type": row.device_type,
                    "steps_sum": int(row.steps_sum) if row.steps_sum is not None else None,
                    "active_energy_sum": float(row.active_energy_sum) if row.active_energy_sum is not None else None,
                    "basal_energy_sum": float(row.basal_energy_sum) if row.basal_energy_sum is not None else None,
                    "total_energy_sum": float(row.total_energy_sum) if row.total_energy_sum is not None else None,
                    "hr_avg": int(round(float(row.hr_avg))) if row.hr_avg is not None else None,
                    "hr_max": None,  # Not available in simplified archive
                    "hr_min": None,  # Not available in simplified archive
                    "distance_sum": float(row.distance_sum) if row.distance_sum is not None else None,
                    "flights_climbed_sum": int(row.flights_climbed_sum)
                    if row.flights_climbed_sum is not None
                    else None,
                    "active_time_minutes": int(row.active_time_sum) if row.active_time_sum is not None else None,
                }
            )
        return aggregates


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
