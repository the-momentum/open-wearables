from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import TextClause, text

from app.constants.series_types.workout_detail_stats import WORKOUT_DETAIL_STATS
from app.database import DbSession
from app.schemas.enums import ProviderName, SeriesType, get_series_type_id

# workout_details columns per series, so a series' statistics land in one row.
_WORKOUT_COLUMNS: dict[SeriesType, dict[str, str]] = defaultdict(dict)
for _column, (_series_type, _stat) in WORKOUT_DETAIL_STATS.items():
    _WORKOUT_COLUMNS[_series_type][_stat] = _column

# Rows changed per statement in the long-running updates, so no transaction holds a source for long.
UPDATE_BATCH_SIZE = 20_000
# A data_migration row per data source the backfill gave up on; retention leaves that source's history alone.
SKIPPED_SOURCE = "aggregate_backfill:skipped:"

# A batch of one source's legacy speeds, km/h back to m/s; the speed row it writes alongside is what makes a
# workout done, so a batch repeated after a crash finds nothing left to divide.
_SUUNTO_SPEED = text("""
    WITH divided AS (
        UPDATE workout_details wd
        SET average_speed = round(wd.average_speed / 3.6, 2), max_speed = round(wd.max_speed / 3.6, 2)
        WHERE wd.record_id IN (
            SELECT d.record_id FROM workout_details d JOIN event_record er ON er.id = d.record_id
            WHERE er.data_source_id = :source AND er.category = 'workout'
                AND (d.average_speed IS NOT NULL OR d.max_speed IS NOT NULL)
                AND NOT EXISTS (
                    SELECT 1 FROM event_record_aggregate a
                    WHERE a.record_id = d.record_id AND a.series_type_definition_id = :speed
                )
            LIMIT :limit
        )
        RETURNING wd.record_id, wd.average_speed, wd.max_speed
    )
    INSERT INTO event_record_aggregate (id, record_id, series_type_definition_id, computed_by, avg, max, count)
    SELECT gen_random_uuid(), record_id, :speed, 'provider', average_speed, max_speed, 1 FROM divided
    ON CONFLICT ON CONSTRAINT uq_event_record_aggregate_record_type_computed_by DO NOTHING
""")

# Probed per data source: a DISTINCT over the join read every workout of every source for each page.
_SOURCES_WITH_WORKOUTS = text("""
    SELECT ds.id, ds.provider FROM data_source ds
    WHERE ds.id > :after AND EXISTS (
        SELECT 1 FROM event_record er JOIN workout_details wd ON wd.record_id = er.id
        WHERE er.data_source_id = ds.id AND er.category = 'workout'
    )
    ORDER BY ds.id LIMIT :limit
""")

_PROVIDER_SOURCES = text(
    "SELECT id FROM data_source WHERE provider = :provider AND id > :after ORDER BY id LIMIT :limit"
)

_ARCHIVE_SOURCES = text("""
    SELECT ds.id FROM data_source ds
    WHERE ds.id > :after AND EXISTS (SELECT 1 FROM data_point_series_archive a WHERE a.data_source_id = ds.id)
    ORDER BY ds.id LIMIT :limit
""")

_FIRST_WORKOUT = text(
    "SELECT min(start_datetime) FROM event_record WHERE data_source_id = :source AND category = 'workout'"
)
_FIRST_ARCHIVED = text("SELECT min(bucket_start_at) FROM data_point_series_archive WHERE data_source_id = :source")

# A legacy epoch sample: its external_id is "{device prefix}-{hex(start)}" and the hex is its own timestamp.
# One series' next rows after :after in time, so each batch reads only its own range of the index.
_GARMIN_EPOCH_WINDOWS = text("""
    WITH batch AS (
        SELECT s.id, s.recorded_at, s.window_seconds IS NULL AND s.is_daily_total IS NOT TRUE
            AND s.external_id ~ '^[^-]+-[0-9a-f]+$'
            AND split_part(s.external_id, '-', 2) = to_hex(extract(epoch FROM s.recorded_at)::bigint) AS epoch
        FROM series_sample s
        WHERE s.data_source_id = :source AND s.series_type_definition_id = :type AND s.recorded_at > :after
        ORDER BY s.recorded_at LIMIT :limit
    ), widened AS (
        UPDATE series_sample s SET window_seconds = 900 FROM batch WHERE s.id = batch.id AND batch.epoch
    )
    SELECT max(recorded_at) FROM batch
""")

# The archive kept one statistic per row; a day's rows become one open_wearables row at the UTC day it was.
_ARCHIVE_DAYS = text("""
    INSERT INTO series_aggregate (
        id, data_source_id, series_type_definition_id, period_kind, period_start, period_end, zone_offset,
        computed_by, sum, avg, max, count
    )
    SELECT gen_random_uuid(), a.data_source_id, a.series_type_definition_id, 'day', a.bucket_start_at,
        a.bucket_start_at + interval '1 day', '+00:00', 'open_wearables',
        max(a.value) FILTER (WHERE a.aggregation_type = 'sum'),
        max(a.value) FILTER (WHERE a.aggregation_type = 'avg'),
        max(a.value) FILTER (WHERE a.aggregation_type = 'max'),
        max(a.sample_count)
    FROM data_point_series_archive a
    WHERE a.data_source_id = :source AND a.bucket_start_at >= :lo AND a.bucket_start_at < :hi
    GROUP BY a.data_source_id, a.series_type_definition_id, a.bucket_start_at
    ON CONFLICT ON CONSTRAINT uq_series_aggregate_source_type_period_computed_by DO NOTHING
""")


def _workout_series_insert(series_type: SeriesType, columns: dict[str, str]) -> TextClause:
    """One series of a source's workout_details as provider rows; a statistic already stored is kept."""
    stats = sorted(columns)
    return text(f"""
        INSERT INTO event_record_aggregate
            (id, record_id, series_type_definition_id, computed_by, {", ".join(stats)}, count)
        SELECT gen_random_uuid(), wd.record_id, {get_series_type_id(series_type)}, 'provider',
            {", ".join(f"wd.{columns[stat]}" for stat in stats)}, 1
        FROM workout_details wd JOIN event_record er ON er.id = wd.record_id
        WHERE er.data_source_id = :source AND er.start_datetime >= :lo AND er.start_datetime < :hi
            AND ({" OR ".join(f"wd.{columns[stat]} IS NOT NULL" for stat in stats)})
        ON CONFLICT ON CONSTRAINT uq_event_record_aggregate_record_type_computed_by DO UPDATE SET
            {", ".join(f"{stat} = coalesce(event_record_aggregate.{stat}, EXCLUDED.{stat})" for stat in stats)}
    """)


_WORKOUT_INSERTS = {
    series_type: _workout_series_insert(series_type, cols) for series_type, cols in _WORKOUT_COLUMNS.items()
}
_WORKOUT_ENERGY_INSERTS = {
    series_type: _workout_series_insert(series_type, {"sum": "energy_burned"})
    for series_type in (SeriesType.active_energy, SeriesType.total_energy)
}


class AggregateBackfillRepository:
    """SQL of the one-off backfill into the aggregate tables. Every statement is bounded (a batch, or one source's
    window of time) and safe to repeat."""

    def provider_sources(self, db_session: DbSession, provider: ProviderName, after: UUID, limit: int) -> list[UUID]:
        params = {"provider": provider.value, "after": after, "limit": limit}
        return list(db_session.execute(_PROVIDER_SOURCES, params).scalars())

    def divide_suunto_speed(self, db_session: DbSession, source_id: UUID) -> int:
        """A batch of the source's speeds stored in km/h before the fix, back to m/s; returns the workouts divided."""
        params = {"source": source_id, "speed": get_series_type_id(SeriesType.speed), "limit": UPDATE_BATCH_SIZE}
        return db_session.execute(_SUUNTO_SPEED, params).rowcount  # ty: ignore[unresolved-attribute]

    def sources_with_workouts(self, db_session: DbSession, after: UUID, limit: int) -> list[tuple[UUID, str]]:
        return [
            (row.id, row.provider)
            for row in db_session.execute(_SOURCES_WITH_WORKOUTS, {"after": after, "limit": limit})
        ]

    def first_workout(self, db_session: DbSession, source_id: UUID) -> datetime | None:
        return db_session.execute(_FIRST_WORKOUT, {"source": source_id}).scalar()

    def mirror_workout_details(
        self, db_session: DbSession, source_id: UUID, energy_series: SeriesType | None, lo: datetime, hi: datetime
    ) -> None:
        """The workout_details statistics of the source's workouts started in [lo, hi) into event_record_aggregate,
        and their energy in ``energy_series`` where the provider's is established."""
        params = {"source": source_id, "lo": lo, "hi": hi}
        for statement in _WORKOUT_INSERTS.values():
            db_session.execute(statement, params)
        if energy_series is not None:
            db_session.execute(_WORKOUT_ENERGY_INSERTS[energy_series], params)

    def set_garmin_epoch_windows(
        self, db_session: DbSession, source_id: UUID, series_type: SeriesType, after: datetime
    ) -> datetime | None:
        """The legacy epochs among the series' next batch after ``after`` get their 15-minute width; returns the
        batch's last instant, None once nothing is left."""
        params = {"source": source_id, "type": get_series_type_id(series_type), "after": after}
        return db_session.execute(_GARMIN_EPOCH_WINDOWS, {**params, "limit": UPDATE_BATCH_SIZE}).scalar()

    def archive_sources(self, db_session: DbSession, after: UUID, limit: int) -> list[UUID]:
        return list(db_session.execute(_ARCHIVE_SOURCES, {"after": after, "limit": limit}).scalars())

    def first_archived(self, db_session: DbSession, source_id: UUID) -> datetime | None:
        return db_session.execute(_FIRST_ARCHIVED, {"source": source_id}).scalar()

    def copy_archive_days(self, db_session: DbSession, source_id: UUID, lo: datetime, hi: datetime) -> int:
        """The source's days archived in [lo, hi) as open_wearables day rows; a day the rollup already holds is
        kept."""
        params = {"source": source_id, "lo": lo, "hi": hi}
        return db_session.execute(_ARCHIVE_DAYS, params).rowcount  # ty: ignore[unresolved-attribute]
