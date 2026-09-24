#!/usr/bin/env python3
"""Re-key existing Whoop whole-day strain and energy onto the day the cycle covers.

Both were written with recorded_at = the cycle's start. A Whoop cycle runs from one
sleep onset to the next, so for anyone who falls asleep before local midnight the start
sits on the previous day: the value lands a day early, and when bedtime drifts across
midnight two cycles collapse onto one date -- that day double-counts and the next is
left empty (#1554). normalize_cycle now keys on the midpoint's local date, stored as
local midnight; this brings the existing rows onto the same key.

The cycle's end is recovered without refetching: cycle[n].end == cycle[n+1].start ==
the next non-nap sleep's onset, verified against raw payloads. Where the next onset is
more than 30h out it belongs to a later cycle (device off), so the span falls back to
start + 24h, which is what Whoop itself synthesizes for a day it has no sleep for.

Two rows can want the same new key: either two cycles resolve to one date, or the date
is already held by a row this migration does not touch. Both are left alone and
reported rather than merged or overwritten -- neither should occur in practice, and a
score is worth more than a tidy count.

Idempotent: eligibility is "recorded_at is not local midnight", which is exactly what a
migrated row is not. Cycles Whoop synthesized on local-midnight boundaries are already
on the right key and are skipped for the same reason.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/rekey_whoop_cycle_days.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/rekey_whoop_cycle_days.py
"""

import argparse
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

# Whoop's longest real cycle is ~29h; past that the next onset opens a later cycle.
_MAX_CYCLE_SPAN = "30 hours"


@dataclass(frozen=True)
class _Table:
    """One table's worth of cycle-derived rows, and how to find their owner."""

    name: str
    label: str
    eligible: str  # identifies whole-day cycle rows
    user_id: str  # expression yielding the owning user
    key: str  # the columns the unique constraint scopes recorded_at by


_HEALTH_SCORE = _Table(
    name="health_score",
    label="health_score (strain)",
    # percent_recorded is on WorkoutScore and never on CycleScore, so it excludes the
    # legacy workout strain that backfill_whoop_strain_event_record.py could not link.
    eligible=(
        "t.provider = 'whoop' AND t.category = 'strain' AND t.event_record_id IS NULL"
        " AND NOT (t.components ? 'percent_recorded')"
    ),
    user_id="t.user_id",
    key="t.user_id, t.provider, t.category",
)

_DATA_POINT_SERIES = _Table(
    name="data_point_series",
    label="data_point_series (active_energy)",
    eligible=(
        "t.is_daily_total IS TRUE"
        " AND EXISTS (SELECT 1 FROM data_source ds WHERE ds.id = t.data_source_id AND ds.provider = 'whoop')"
        " AND EXISTS (SELECT 1 FROM series_type_definition std"
        "             WHERE std.id = t.series_type_definition_id AND std.code = 'active_energy')"
    ),
    user_id="(SELECT ds.user_id FROM data_source ds WHERE ds.id = t.data_source_id)",
    key="t.data_source_id, t.series_type_definition_id",
)


def _mapping(table: _Table) -> str:
    """Every eligible row with the local midnight it belongs on, ranked within its day."""
    return f"""
        SELECT t.*,
               c.cycle_end,
               d.new_recorded_at,
               row_number() OVER (
                   PARTITION BY {table.key}, d.new_recorded_at
                   ORDER BY least(c.cycle_end, d.new_recorded_at + interval '1 day')
                          - greatest(t.recorded_at, d.new_recorded_at) DESC,
                            t.recorded_at DESC
               ) AS rank
        FROM {table.name} t
        CROSS JOIN LATERAL (
            SELECT cast(coalesce(t.zone_offset, '+00:00') AS interval) AS off
        ) o
        CROSS JOIN LATERAL (
            SELECT CASE
                       WHEN n.onset IS NOT NULL AND n.onset <= t.recorded_at + interval '{_MAX_CYCLE_SPAN}'
                       THEN n.onset
                       ELSE t.recorded_at + interval '24 hours'
                   END AS cycle_end
            FROM (
                SELECT min(er.start_datetime) AS onset
                FROM data_source ds
                JOIN event_record er ON er.data_source_id = ds.id
                JOIN sleep_details sd ON sd.record_id = er.id
                WHERE ds.user_id = {table.user_id}
                  AND ds.provider = 'whoop'
                  AND er.category = 'sleep'
                  AND sd.is_nap IS NOT TRUE
                  AND er.start_datetime > t.recorded_at
            ) n
        ) c
        CROSS JOIN LATERAL (
            SELECT ((
                (((t.recorded_at + (c.cycle_end - t.recorded_at) / 2 + o.off) AT TIME ZONE 'UTC')::date)::timestamp
                - o.off
            ) AT TIME ZONE 'UTC') AS new_recorded_at
        ) d
        WHERE {table.eligible}
          AND ((t.recorded_at + o.off) AT TIME ZONE 'UTC')::time <> '00:00:00'
    """


def _movable(table: _Table) -> str:
    """The mapping, minus rows whose target is contested. Reported, not merged."""
    return f"""
        SELECT m.* FROM ({_mapping(table)}) m
        WHERE m.rank = 1
          AND NOT EXISTS (
              SELECT 1 FROM {table.name} x
              WHERE ({table.key.replace("t.", "x.")}) IS NOT DISTINCT FROM ({table.key.replace("t.", "m.")})
                AND x.recorded_at = m.new_recorded_at
                AND x.id <> m.id
          )
    """


def _rekey(db: Session, table: _Table, *, dry_run: bool) -> int:
    eligible, contested = db.execute(
        text(f"""
            SELECT count(*), count(*) FILTER (WHERE id NOT IN (SELECT id FROM ({_movable(table)}) v))
            FROM ({_mapping(table)}) m
        """)
    ).one()
    if not eligible:
        print(f"{table.label}: nothing to do -- no start-keyed Whoop cycle rows found.")
        return 0

    print(f"{table.label}: {eligible} row(s) eligible, {contested} left alone (target already taken)")
    for old, new in db.execute(
        text(f"SELECT recorded_at, new_recorded_at FROM ({_movable(table)}) v ORDER BY recorded_at DESC LIMIT 5")
    ):
        print(f"    {old} -> {new}")
    if dry_run:
        return 0

    moved = db.execute(
        text(f"""
            UPDATE {table.name} tgt
            SET recorded_at = v.new_recorded_at
            FROM ({_movable(table)}) v
            WHERE tgt.id = v.id
        """)
    ).rowcount  # ty: ignore[unresolved-attribute]
    print(f"  re-keyed {moved}")
    return moved


def rekey_whoop_cycle_days(db: Session, *, dry_run: bool) -> int:
    """Re-key Whoop cycle rows onto the day they cover. Does not commit -- caller owns the transaction."""
    moved = sum(_rekey(db, table, dry_run=dry_run) for table in (_HEALTH_SCORE, _DATA_POINT_SERIES))
    if dry_run:
        print("\nDry run -- no changes made.")
    return moved


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        moved = rekey_whoop_cycle_days(db, dry_run=dry_run)
        if dry_run or not moved:
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
