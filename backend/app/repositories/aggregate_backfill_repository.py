from collections import defaultdict
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

_SUUNTO_SPEED = text("""
    UPDATE workout_details wd
    SET average_speed = round(wd.average_speed / 3.6, 2), max_speed = round(wd.max_speed / 3.6, 2)
    FROM event_record er JOIN data_source ds ON ds.id = er.data_source_id
    WHERE wd.record_id = er.id AND ds.provider = :provider
        AND (wd.average_speed IS NOT NULL OR wd.max_speed IS NOT NULL)
        AND NOT EXISTS (
            SELECT 1 FROM event_record_aggregate a
            WHERE a.record_id = wd.record_id AND a.series_type_definition_id = :speed
        )
""")

_SOURCES_WITH_WORKOUTS = text("""
    SELECT DISTINCT ds.id, ds.provider FROM data_source ds JOIN event_record er ON er.data_source_id = ds.id
    JOIN workout_details wd ON wd.record_id = er.id
    WHERE ds.id > :after ORDER BY ds.id LIMIT :limit
""")

_GARMIN_SOURCES = text("SELECT id FROM data_source WHERE provider = :provider AND id > :after ORDER BY id LIMIT :limit")

_ARCHIVE_SOURCES = text("""
    SELECT DISTINCT data_source_id FROM data_point_series_archive WHERE data_source_id > :after
    ORDER BY data_source_id LIMIT :limit
""")

# A legacy epoch sample: its external_id is "{device prefix}-{hex(start)}" and the hex is its own timestamp.
_GARMIN_EPOCH_WINDOWS = text("""
    UPDATE series_sample SET window_seconds = 900
    WHERE id IN (
        SELECT s.id FROM series_sample s
        WHERE s.data_source_id = :source AND s.series_type_definition_id = ANY(:types)
            AND s.window_seconds IS NULL AND s.is_daily_total IS NOT TRUE
            AND s.external_id ~ '^[^-]+-[0-9a-f]+$'
            AND split_part(s.external_id, '-', 2) = to_hex(extract(epoch FROM s.recorded_at)::bigint)
        LIMIT :limit
    )
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
    WHERE a.data_source_id = :source
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
        WHERE er.data_source_id = :source AND ({" OR ".join(f"wd.{columns[stat]} IS NOT NULL" for stat in stats)})
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
    """SQL of the one-off backfill into the aggregate tables. Every statement is safe to repeat except the Suunto
    speed fix, which the caller commits together with its completion marker."""

    def divide_suunto_speed(self, db_session: DbSession) -> int:
        """Suunto workout speed stored in km/h before the fix, back to m/s; workouts already mirrored are m/s."""
        params = {"provider": ProviderName.SUUNTO.value, "speed": get_series_type_id(SeriesType.speed)}
        return db_session.execute(_SUUNTO_SPEED, params).rowcount  # ty: ignore[unresolved-attribute]

    def sources_with_workouts(self, db_session: DbSession, after: UUID, limit: int) -> list[tuple[UUID, str]]:
        return [
            (row.id, row.provider)
            for row in db_session.execute(_SOURCES_WITH_WORKOUTS, {"after": after, "limit": limit})
        ]

    def mirror_workout_details(self, db_session: DbSession, source_id: UUID, energy_series: SeriesType | None) -> None:
        """Every workout_details statistic of the source into event_record_aggregate, and its energy in
        ``energy_series`` where the provider's is established."""
        for statement in _WORKOUT_INSERTS.values():
            db_session.execute(statement, {"source": source_id})
        if energy_series is not None:
            db_session.execute(_WORKOUT_ENERGY_INSERTS[energy_series], {"source": source_id})

    def garmin_sources(self, db_session: DbSession, after: UUID, limit: int) -> list[UUID]:
        params = {"provider": ProviderName.GARMIN.value, "after": after, "limit": limit}
        return list(db_session.execute(_GARMIN_SOURCES, params).scalars())

    def set_garmin_epoch_windows(self, db_session: DbSession, source_id: UUID, epoch_types: list[SeriesType]) -> int:
        """One batch of a source's legacy epoch samples gets its 15-minute width; returns the rows updated."""
        types = [get_series_type_id(series_type) for series_type in epoch_types]
        params = {"source": source_id, "types": types, "limit": UPDATE_BATCH_SIZE}
        return db_session.execute(_GARMIN_EPOCH_WINDOWS, params).rowcount  # ty: ignore[unresolved-attribute]

    def archive_sources(self, db_session: DbSession, after: UUID, limit: int) -> list[UUID]:
        return list(db_session.execute(_ARCHIVE_SOURCES, {"after": after, "limit": limit}).scalars())

    def copy_archive_days(self, db_session: DbSession, source_id: UUID) -> int:
        """The source's archived days as open_wearables day rows; a day the rollup already holds is kept."""
        return db_session.execute(_ARCHIVE_DAYS, {"source": source_id}).rowcount  # ty: ignore[unresolved-attribute]
