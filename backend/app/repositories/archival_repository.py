"""Repository for archival settings and archive table operations."""

import time
import uuid
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, case, cast, func, text
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataPointSeries, DataPointSeriesArchive, DataSource
from app.models.archival_setting import ArchivalSetting
from app.schemas.series_types import (
    AGGREGATION_METHOD_BY_TYPE,
    AggregationMethod,
    SeriesType,
    get_series_type_from_id,
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

    def update(self, db: DbSession, archive_after_days: int | None, delete_after_days: int | None) -> ArchivalSetting:
        """Update archival settings."""
        setting = self.get(db)
        setting.archive_after_days = archive_after_days
        setting.delete_after_days = delete_after_days
        db.commit()
        db.refresh(setting)
        return setting


# ---------------------------------------------------------------------------
# Data-point archive repository
# ---------------------------------------------------------------------------

ARCHIVE_BATCH_SIZE = 5_000
# Safety limits to prevent overloading the DB on initial runs
MAX_ROWS_PER_RUN = 500_000  # Stop after archiving this many rows per invocation
MAX_SECONDS_PER_RUN = 120  # Stop after this many seconds per invocation


class DataPointSeriesArchiveRepository:
    """Handles aggregation, insertion, and deletion for the archive table."""

    def get_storage_estimate(self, db: DbSession) -> dict:
        """Get storage sizes for ALL user tables from pg_catalog.

        Returns live / archive / other breakdowns so the frontend can visualise
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
        archive_data_bytes = 0
        archive_index_bytes = 0
        archive_rows = 0
        other_bytes = 0

        for row in result:
            if row.relname == "data_point_series":
                live_data_bytes = row.data_bytes
                live_index_bytes = row.index_bytes
                live_rows = row.row_count
            elif row.relname == "data_point_series_archive":
                archive_data_bytes = row.data_bytes
                archive_index_bytes = row.index_bytes
                archive_rows = row.row_count
            else:
                other_bytes += row.total_bytes

        # Query the actual date span of live data for accurate estimation.
        live_span_days = 0
        if live_rows > 0:
            span = db.execute(
                text("""
                    SELECT EXTRACT(DAY FROM MAX(recorded_at) - MIN(recorded_at))::int AS span
                    FROM data_point_series
                """)
            ).scalar()
            live_span_days = max(span or 0, 1)

        live_total = live_data_bytes + live_index_bytes
        archive_total = archive_data_bytes + archive_index_bytes
        total = live_total + archive_total + other_bytes

        avg_live = (live_total / live_rows) if live_rows else 0.0
        avg_archive = (archive_total / archive_rows) if archive_rows else 0.0

        return {
            "live_data_bytes": live_data_bytes,
            "live_index_bytes": live_index_bytes,
            "archive_data_bytes": archive_data_bytes,
            "archive_index_bytes": archive_index_bytes,
            "other_tables_bytes": other_bytes,
            "total_bytes": total,
            "live_row_count": live_rows,
            "archive_row_count": archive_rows,
            "avg_bytes_per_live_row": round(avg_live, 1),
            "avg_bytes_per_archive_row": round(avg_archive, 1),
            "live_data_span_days": live_span_days,
            "live_total_pretty": _pretty_bytes(live_total),
            "live_data_pretty": _pretty_bytes(live_data_bytes),
            "live_index_pretty": _pretty_bytes(live_index_bytes),
            "archive_total_pretty": _pretty_bytes(archive_total),
            "archive_data_pretty": _pretty_bytes(archive_data_bytes),
            "archive_index_pretty": _pretty_bytes(archive_index_bytes),
            "other_tables_pretty": _pretty_bytes(other_bytes),
            "total_pretty": _pretty_bytes(total),
        }

    def archive_data_before(self, db: DbSession, cutoff_date: date) -> int:
        """Aggregate live rows older than *cutoff_date* into the archive table.

        For each (data_source_id, series_type_definition_id, date):
        1. Compute the aggregate value using the type's AggregationMethod (sum/avg/max).
        2. UPSERT into archive table (on conflict → update with re-calculated value).
        3. DELETE original live rows.

        Safety: stops after MAX_ROWS_PER_RUN rows or MAX_SECONDS_PER_RUN seconds
        to avoid overwhelming the server on the first run. The next Celery
        invocation will continue where this one left off.

        Returns the number of live rows removed.
        """
        total_deleted = 0
        start_time = time.monotonic()

        # Process in batches to avoid excessive memory usage
        while True:
            # Safety check: stop if we've processed enough or taken too long
            elapsed = time.monotonic() - start_time
            if total_deleted >= MAX_ROWS_PER_RUN:
                break
            if elapsed >= MAX_SECONDS_PER_RUN:
                break

            # Step 1: Find data_source_ids with archivable data (batch by source)
            source_ids = (
                db.query(DataPointSeries.data_source_id)
                .filter(cast(DataPointSeries.recorded_at, Date) < cutoff_date)
                .distinct()
                .limit(10)
                .all()
            )

            if not source_ids:
                break

            source_id_list = [s[0] for s in source_ids]

            # Step 2: Group by (source, type, date) and compute all aggregates
            # We'll post-process to select the correct one per type
            raw_aggregates = (
                db.query(
                    DataPointSeries.data_source_id,
                    DataPointSeries.series_type_definition_id,
                    cast(DataPointSeries.recorded_at, Date).label("date"),
                    func.avg(DataPointSeries.value).label("avg_value"),
                    func.min(DataPointSeries.value).label("min_value"),
                    func.max(DataPointSeries.value).label("max_value"),
                    func.sum(DataPointSeries.value).label("sum_value"),
                    func.count(DataPointSeries.id).label("sample_count"),
                )
                .filter(
                    DataPointSeries.data_source_id.in_(source_id_list),
                    cast(DataPointSeries.recorded_at, Date) < cutoff_date,
                )
                .group_by(
                    DataPointSeries.data_source_id,
                    DataPointSeries.series_type_definition_id,
                    cast(DataPointSeries.recorded_at, Date),
                )
                .all()
            )

            if not raw_aggregates:
                break

            # Step 3: For each group, pick the correct aggregate column based on series type
            values_list = []
            for row in raw_aggregates:
                try:
                    series_type = get_series_type_from_id(row.series_type_definition_id)
                    method = AGGREGATION_METHOD_BY_TYPE.get(series_type, AggregationMethod.AVG)

                    if method == AggregationMethod.SUM:
                        value = row.sum_value
                    elif method == AggregationMethod.MAX:
                        value = row.max_value
                    else:  # AVG
                        value = row.avg_value

                    values_list.append(
                        {
                            "id": _deterministic_uuid(row.data_source_id, row.series_type_definition_id, row.date),
                            "data_source_id": row.data_source_id,
                            "series_type_definition_id": row.series_type_definition_id,
                            "date": row.date,
                            "value": value,
                            "sample_count": row.sample_count,
                        }
                    )
                except KeyError:
                    # Unknown series type ID — skip this aggregate but don't
                    # delete the corresponding live rows either.
                    continue

            if not values_list:
                # All series types in this batch were unknown — skip without
                # deleting to avoid data loss.
                continue

            # Step 4: Upsert into archive
            for i in range(0, len(values_list), ARCHIVE_BATCH_SIZE):
                chunk = values_list[i : i + ARCHIVE_BATCH_SIZE]
                stmt = insert(DataPointSeriesArchive).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_archive_source_type_date",
                    set_={
                        "value": stmt.excluded.value,
                        "sample_count": stmt.excluded.sample_count,
                    },
                )
                db.execute(stmt)

            # Step 5: Delete the live rows we just archived
            deleted_count = (
                db.query(DataPointSeries)
                .filter(
                    DataPointSeries.data_source_id.in_(source_id_list),
                    cast(DataPointSeries.recorded_at, Date) < cutoff_date,
                )
                .delete(synchronize_session=False)
            )
            total_deleted += deleted_count

            db.commit()

        return total_deleted

    def delete_archive_before(self, db: DbSession, cutoff_date: date) -> int:
        """Permanently delete archive rows older than *cutoff_date*.

        Returns the number of rows deleted.
        """
        deleted = (
            db.query(DataPointSeriesArchive)
            .filter(DataPointSeriesArchive.date < cutoff_date)
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted

    def delete_live_before(self, db: DbSession, cutoff_date: date) -> int:
        """Permanently delete live rows older than *cutoff_date*.

        Used when retention policy is active without archival — data is
        simply discarded instead of being aggregated first.

        Uses a subquery + DELETE pattern because PostgreSQL does not support
        ``DELETE ... LIMIT`` and SQLAlchemy's ``Query.delete()`` rejects
        queries with ``.limit()``.

        Respects the same safety limits as archive_data_before.

        Returns the number of live rows deleted.
        """
        total_deleted = 0
        start_time = time.monotonic()

        while True:
            elapsed = time.monotonic() - start_time
            if total_deleted >= MAX_ROWS_PER_RUN or elapsed >= MAX_SECONDS_PER_RUN:
                break

            ids_to_delete = (
                db.query(DataPointSeries.id)
                .filter(cast(DataPointSeries.recorded_at, Date) < cutoff_date)
                .limit(ARCHIVE_BATCH_SIZE)
                .subquery()
            )
            deleted = (
                db.query(DataPointSeries)
                .filter(DataPointSeries.id.in_(ids_to_delete))
                .delete(synchronize_session=False)
            )

            if deleted == 0:
                break

            total_deleted += deleted
            db.commit()

        return total_deleted

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
        energy_id = get_series_type_id(SeriesType.energy)
        basal_energy_id = get_series_type_id(SeriesType.basal_energy)
        hr_id = get_series_type_id(SeriesType.heart_rate)
        distance_id = get_series_type_id(SeriesType.distance_walking_running)
        flights_id = get_series_type_id(SeriesType.flights_climbed)

        results = (
            db.query(
                DataPointSeriesArchive.date.label("activity_date"),
                DataSource.source.label("source"),
                DataSource.device_model.label("device_model"),
                func.sum(
                    case(
                        (DataPointSeriesArchive.series_type_definition_id == steps_id, DataPointSeriesArchive.value),
                        else_=0,
                    )
                ).label("steps_sum"),
                func.sum(
                    case(
                        (DataPointSeriesArchive.series_type_definition_id == energy_id, DataPointSeriesArchive.value),
                        else_=0,
                    )
                ).label("active_energy_sum"),
                func.sum(
                    case(
                        (
                            DataPointSeriesArchive.series_type_definition_id == basal_energy_id,
                            DataPointSeriesArchive.value,
                        ),
                        else_=0,
                    )
                ).label("basal_energy_sum"),
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
            )
            .join(DataSource, DataPointSeriesArchive.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                DataPointSeriesArchive.date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                DataPointSeriesArchive.date < end_date.date() if isinstance(end_date, datetime) else end_date,
                DataPointSeriesArchive.series_type_definition_id.in_(series_type_ids),
            )
            .group_by(
                DataPointSeriesArchive.date,
                DataSource.source,
                DataSource.device_model,
            )
            .all()
        )

        aggregates = []
        for row in results:
            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "steps_sum": int(row.steps_sum) if row.steps_sum else 0,
                    "active_energy_sum": float(row.active_energy_sum) if row.active_energy_sum else 0.0,
                    "basal_energy_sum": float(row.basal_energy_sum) if row.basal_energy_sum else 0.0,
                    "hr_avg": int(round(float(row.hr_avg))) if row.hr_avg is not None else None,
                    "hr_max": None,  # Not available in simplified archive
                    "hr_min": None,  # Not available in simplified archive
                    "distance_sum": float(row.distance_sum) if row.distance_sum is not None else None,
                    "flights_climbed_sum": int(row.flights_climbed_sum)
                    if row.flights_climbed_sum is not None
                    else None,
                }
            )
        return aggregates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pretty_bytes(n: int) -> str:
    """Return a human-readable byte string (e.g. '1.23 GB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.2f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.2f} PB"


def _deterministic_uuid(data_source_id: UUID, series_type_id: int, d: date) -> UUID:
    """Generate a deterministic UUID v5 for an archive row so upserts are idempotent."""
    namespace = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    name = f"{data_source_id}:{series_type_id}:{d.isoformat()}"
    return uuid.uuid5(namespace, name)
