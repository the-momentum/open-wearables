from collections import defaultdict
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import TextClause, text

from app.constants.series_types.history_rules import HISTORY_RULES, DayAnchor, HistoryRule, SessionMatch
from app.constants.series_types.workout_detail_stats import WORKOUT_DETAIL_STATS
from app.database import DbSession
from app.schemas.enums import ProviderName, SeriesType, get_series_type_id
from app.schemas.enums.aggregation_method import get_aggregation_method

# workout_details columns per series, so a series' statistics land in one row.
_WORKOUT_COLUMNS: dict[SeriesType, dict[str, str]] = defaultdict(dict)
for _column, (_series_type, _stat) in WORKOUT_DETAIL_STATS.items():
    _WORKOUT_COLUMNS[_series_type][_stat] = _column

# Rows changed per statement in the long-running updates, so no transaction holds a source for long.
UPDATE_BATCH_SIZE = 20_000

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

    def history_sources(self, db_session: DbSession, after: UUID, limit: int) -> list[tuple[UUID, str]]:
        """Data sources of the providers whose history holds day or session values as samples."""
        params = {"providers": _HISTORY_PROVIDERS, "after": after, "limit": limit}
        return [(row.id, row.provider) for row in db_session.execute(_HISTORY_SOURCES, params)]

    def copy_history_values(self, db_session: DbSession, source_id: UUID, provider: str, since: datetime | None) -> int:
        """The source's day and session values stored as samples (from ``since`` on, or all) as provider rows in the
        aggregate tables, where the provider holds none yet. Returns the rows written."""
        written = 0
        for rule, statement in _HISTORY:
            if ProviderName(provider) not in rule.providers:
                continue
            params = {
                "source": source_id,
                "types": [get_series_type_id(series_type) for series_type, _ in rule.series],
                "since": since,
                **_stat_params(rule),
            }
            written += db_session.execute(statement, params).rowcount  # ty: ignore[unresolved-attribute]
        return written

    def delete_copied_samples(
        self, db_session: DbSession, source_id: UUID, provider: str, cutoff: datetime
    ) -> set[tuple[UUID, date]]:
        """The source's history samples the backfill copied, recorded before ``cutoff``, deleted where the provider's
        aggregate row holds the very same value at the very same instant (its period start, or the session's end), so
        nothing the sample said is lost. Returns the (source, local day) pairs they were on."""
        days: set[tuple[UUID, date]] = set()
        for rule, statement in _DELETES:
            if ProviderName(provider) not in rule.providers:
                continue
            params = {
                "source": source_id,
                "types": [get_series_type_id(series_type) for series_type, _ in rule.series],
                "since": None,
                "cutoff": cutoff,
                **_stat_params(rule),
            }
            days.update((row.data_source_id, row.day) for row in db_session.execute(statement, params))
        return days


_DAYS = {
    DayAnchor.LOCAL: "((s.recorded_at AT TIME ZONE 'UTC') + coalesce(s.zone_offset, '+00:00')::interval)::date",
    DayAnchor.UTC_DATE: "(s.recorded_at AT TIME ZONE 'UTC')::date",
    DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET: "((s.recorded_at AT TIME ZONE 'UTC') + interval '13 hours')::date",
    DayAnchor.NIGHT_STARTED_AT: """((s.recorded_at AT TIME ZONE 'UTC') + coalesce(s.zone_offset, '+00:00')::interval
        + interval '12 hours')::date""",
}
_ZONES = {
    DayAnchor.LOCAL: "coalesce(s.zone_offset, '+00:00')",
    DayAnchor.UTC_DATE: "'+00:00'",
    DayAnchor.NIGHT_STARTED_AT: "coalesce(s.zone_offset, '+00:00')",
    # The offset that puts recorded_at at midnight of its day.
    DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET: f"""(SELECT CASE WHEN o < interval '0' THEN '-' || to_char(-o, 'HH24:MI')
        ELSE '+' || to_char(o, 'HH24:MI') END
        FROM (SELECT {_DAYS[DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET]}::timestamp
            - (s.recorded_at AT TIME ZONE 'UTC') AS o) z)""",
}
_RECORDS = {
    SessionMatch.SLEEP_CONTAINING: """SELECT e.id FROM event_record e
        WHERE e.data_source_id = s.data_source_id AND e.category = 'sleep'
            AND e.start_datetime <= s.recorded_at AND e.end_datetime >= s.recorded_at
        ORDER BY e.end_datetime - e.start_datetime DESC LIMIT 1""",
    SessionMatch.SLEEP_BY_ID_OR_END: """SELECT e.id FROM event_record e
        WHERE e.data_source_id = s.data_source_id AND e.category = 'sleep'
            AND (e.external_id = s.external_id OR e.end_datetime = s.recorded_at)
        ORDER BY (e.external_id = s.external_id) DESC LIMIT 1""",
    SessionMatch.SLEEP_ENDED_BEFORE: """SELECT e.id FROM event_record e LEFT JOIN sleep_details d ON d.record_id = e.id
        WHERE e.data_source_id = s.data_source_id AND e.category = 'sleep' AND d.is_nap IS NOT TRUE
            AND e.end_datetime <= s.recorded_at AND e.end_datetime > s.recorded_at - interval '24 hours'
        ORDER BY e.end_datetime DESC LIMIT 1""",
    SessionMatch.WORKOUT_ENDING: """SELECT e.id FROM event_record e
        WHERE e.data_source_id = s.data_source_id AND e.category = 'workout' AND e.end_datetime = s.recorded_at
        LIMIT 1""",
}
_STATS = ("sum", "avg", "min", "max", "last")
_RULE_SAMPLES = """s.data_source_id = :source AND s.series_type_definition_id = ANY(:types) AND ({where})
    AND (CAST(:since AS timestamptz) IS NULL OR s.recorded_at >= :since)"""
_STAT_VALUES = ", ".join(f"CASE WHEN type_id = ANY(:{stat}_types) THEN value END" for stat in _STATS)


def _day_values(rule: HistoryRule) -> TextClause:
    assert rule.day is not None
    return text(f"""
        WITH src AS (
            SELECT s.data_source_id, s.series_type_definition_id AS type_id, s.value, s.recorded_at,
                {_DAYS[rule.day]} AS day, {_ZONES[rule.day]} AS zone
            FROM series_sample s WHERE {_RULE_SAMPLES.format(where=rule.where)}
        ), days AS (
            -- A day sent more than once (a total re-sent as the day went on) is its latest value.
            SELECT DISTINCT ON (type_id, day) *, (day::timestamp - zone::interval) AT TIME ZONE 'UTC' AS period_start
            FROM src ORDER BY type_id, day, recorded_at DESC
        )
        INSERT INTO series_aggregate (
            id, data_source_id, series_type_definition_id, period_kind, period_start, period_end, zone_offset,
            computed_by, {", ".join(_STATS)}, count
        )
        SELECT gen_random_uuid(), data_source_id, type_id, 'day', period_start, period_start + interval '1 day', zone,
            'provider', {_STAT_VALUES}, 1
        FROM days r
        -- A day the provider already holds, at whatever offset, is kept.
        WHERE NOT EXISTS (
            SELECT 1 FROM series_aggregate a
            WHERE a.data_source_id = r.data_source_id AND a.series_type_definition_id = r.type_id
                AND a.period_kind = 'day' AND a.computed_by = 'provider'
                AND a.period_start BETWEEN r.period_start - interval '28 hours' AND r.period_start + interval '28 hours'
                AND ((a.period_start AT TIME ZONE 'UTC') + a.zone_offset::interval)::date = r.day
        )
        ON CONFLICT ON CONSTRAINT uq_series_aggregate_source_type_period_computed_by DO NOTHING
    """)


def _session_values(rule: HistoryRule) -> TextClause:
    assert rule.session is not None
    return text(f"""
        INSERT INTO event_record_aggregate
            (id, record_id, series_type_definition_id, computed_by, {", ".join(_STATS)}, count)
        SELECT DISTINCT ON (er.id, s.series_type_definition_id) gen_random_uuid(), er.id, s.series_type_definition_id,
            'provider', {_STAT_VALUES.replace("type_id", "s.series_type_definition_id").replace("value", "s.value")}, 1
        FROM series_sample s CROSS JOIN LATERAL ({_RECORDS[rule.session]}) er
        WHERE {_RULE_SAMPLES.format(where=rule.where)}
        ORDER BY er.id, s.series_type_definition_id, s.recorded_at DESC
        ON CONFLICT ON CONSTRAINT uq_event_record_aggregate_record_type_computed_by DO NOTHING
    """)


_HISTORY = [(rule, _day_values(rule) if rule.day else _session_values(rule)) for rule in HISTORY_RULES]
_HISTORY_PROVIDERS = sorted({provider.value for rule in HISTORY_RULES for provider in rule.providers})

_HISTORY_SOURCES = text("""
    SELECT id, provider FROM data_source WHERE provider = ANY(:providers) AND id > :after ORDER BY id LIMIT :limit
""")


def _stat_params(rule: HistoryRule) -> dict[str, list[int]]:
    """Per statistic column, the rule's series whose values go there."""
    params: dict[str, list[int]] = {f"{stat}_types": [] for stat in _STATS}
    for series_type, stat in rule.series:
        column = stat or get_aggregation_method(series_type).value
        params[f"{column}_types"].append(get_series_type_id(series_type))
    return params


# The sample's value in the statistic the rule copied it to; any other statistic of the row is someone else's.
_SAME_VALUE = (
    "s.value = CASE "
    + " ".join(f"WHEN s.series_type_definition_id = ANY(:{stat}_types) THEN a.{stat}" for stat in _STATS)
    + " END"
)


def _delete_day_values(rule: HistoryRule) -> TextClause:
    assert rule.day is not None
    return text(f"""
        DELETE FROM series_sample s
        WHERE {_RULE_SAMPLES.format(where=rule.where)} AND s.recorded_at < :cutoff
            AND EXISTS (
                SELECT 1 FROM series_aggregate a
                WHERE a.data_source_id = s.data_source_id AND a.series_type_definition_id = s.series_type_definition_id
                    AND a.period_kind = 'day' AND a.computed_by = 'provider'
                    AND a.period_start = s.recorded_at
                    AND {_SAME_VALUE}
            )
        RETURNING s.data_source_id, {_DAYS[DayAnchor.LOCAL]} AS day
    """)


def _delete_session_values(rule: HistoryRule) -> TextClause:
    assert rule.session is not None
    return text(f"""
        DELETE FROM series_sample s
        WHERE {_RULE_SAMPLES.format(where=rule.where)} AND s.recorded_at < :cutoff
            AND EXISTS (
                SELECT 1 FROM event_record_aggregate a JOIN event_record e ON e.id = a.record_id
                WHERE a.record_id = ({_RECORDS[rule.session]}) AND e.end_datetime = s.recorded_at
                    AND a.series_type_definition_id = s.series_type_definition_id AND a.computed_by = 'provider'
                    AND {_SAME_VALUE}
            )
        RETURNING s.data_source_id, {_DAYS[DayAnchor.LOCAL]} AS day
    """)


_DELETES = [(rule, _delete_day_values(rule) if rule.day else _delete_session_values(rule)) for rule in HISTORY_RULES]
