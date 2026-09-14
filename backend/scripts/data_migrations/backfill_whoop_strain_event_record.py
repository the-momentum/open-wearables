#!/usr/bin/env python3
"""Link pre-existing Whoop workout strain scores to their event records.

Whoop strain scores were historically written with no FK to the workout they came
from (workouts.py only started stamping event_record_id alongside the health_score
index widening). Those rows are indistinguishable from the per-day cycle strain that
/v2/cycle now produces, since both carry event_record_id IS NULL -- which is exactly
the column meant to tell them apart.

Matching: a legacy row is a workout strain iff its components contain
percent_recorded. Whoop's OpenAPI spec marks percent_recorded required on
WorkoutScore and omits it from CycleScore entirely, so the key is present on every
workout strain and can never appear on a cycle strain. The workout itself is found by
start_datetime = recorded_at (_normalize_strain_health_score derives recorded_at
straight from raw_workout.start), scoped to the same user -- legacy rows have a NULL
data_source_id, so user scoping is what keeps two users' identically-timed workouts
apart.

Skipped rather than guessed: rows matching zero or several workouts, and rows whose
workout already carries a whoop/strain score (linking would violate
uq_health_score_event_record). Those are reported, not deleted -- a health score is
worth more than a tidy count, and the conflict case should be empty in practice.

data_source_id is deliberately left NULL, matching what the live path writes today.

Idempotent and cheap to re-run: the eligibility count short-circuits every later
startup. Linked rows fail event_record_id IS NULL, cycle strain fails the
percent_recorded test, and post-deploy workout strain arrives already linked, so the
candidate set stays empty and no further query runs. Nothing here recomputes a score.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_whoop_strain_event_record.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_whoop_strain_event_record.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

# Legacy rows in scope: Whoop strain, unlinked, carrying the workout-only marker.
_ELIGIBLE = """
    hs.provider = 'whoop'
    AND hs.category = 'strain'
    AND hs.event_record_id IS NULL
    AND hs.components ? 'percent_recorded'
"""

# One row per linkable score. HAVING count(*) = 1 rejects both failure modes at once --
# no matching workout, or an ambiguous match -- which also makes the single array_agg
# element the actual match rather than an arbitrary pick (there is no min(uuid) in
# Postgres). The conflict guard sits outside the grouping so a second candidate still
# counts toward ambiguity even when it is already linked.
_LINKABLE = f"""
    SELECT m.score_id, m.record_id
    FROM (
        SELECT hs.id AS score_id, (array_agg(er.id))[1] AS record_id
        FROM health_score hs
        JOIN data_source ds  ON ds.user_id = hs.user_id
                            AND ds.provider = 'whoop'
        JOIN event_record er ON er.data_source_id = ds.id
                            AND er.category = 'workout'
                            AND er.start_datetime = hs.recorded_at
        WHERE {_ELIGIBLE}
        GROUP BY hs.id
        HAVING count(*) = 1
    ) m
    WHERE NOT EXISTS (
        SELECT 1 FROM health_score x
        WHERE x.event_record_id = m.record_id
          AND x.provider = 'whoop'
          AND x.category = 'strain'
    )
"""

_ELIGIBLE_COUNT = text(f"SELECT count(*) FROM health_score hs WHERE {_ELIGIBLE}")

_LINKABLE_COUNT = text(f"SELECT count(*) FROM ({_LINKABLE}) m")

_UPDATE = text(f"""
    UPDATE health_score hs
    SET event_record_id = m.record_id
    FROM ({_LINKABLE}) m
    WHERE hs.id = m.score_id
""")

# Diagnostics only, so the per-row candidate count is worth its cost here. The NOT IN
# matters for --dry-run, where the linkable rows have not been linked away yet.
_UNRESOLVED_SAMPLE = text(f"""
    SELECT hs.user_id,
           hs.recorded_at,
           (SELECT count(*)
              FROM data_source ds
              JOIN event_record er ON er.data_source_id = ds.id
             WHERE ds.user_id = hs.user_id
               AND ds.provider = 'whoop'
               AND er.category = 'workout'
               AND er.start_datetime = hs.recorded_at) AS matching_workouts
    FROM health_score hs
    WHERE {_ELIGIBLE}
      AND hs.id NOT IN (SELECT m.score_id FROM ({_LINKABLE}) m)
    ORDER BY hs.recorded_at DESC
    LIMIT 10
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query).scalar() or 0


def _report_unresolved(db: Session, unresolved: int) -> None:
    # These never resolve on their own, so the message repeats every startup by design --
    # a standing signal to investigate or drop the script, not a transient warning.
    print(f"Skipped {unresolved} row(s) with no unambiguous, unlinked workout. Sample:")
    for user_id, recorded_at, matches in db.execute(_UNRESOLVED_SAMPLE):
        print(f"  user={user_id} recorded_at={recorded_at} matching_workouts={matches}")


def backfill_whoop_strain(db: Session, *, dry_run: bool) -> int:
    """Link legacy Whoop workout strain scores. Does not commit -- caller owns the transaction.

    In dry-run mode the count comes from an up-front SELECT; in live mode it is the
    rowcount of the UPDATE, so the reported number is what was actually written.
    """
    eligible = _scalar_count(db, _ELIGIBLE_COUNT)
    if not eligible:
        print("Nothing to do -- no unlinked Whoop workout strain scores found.")
        return 0

    if dry_run:
        linkable = _scalar_count(db, _LINKABLE_COUNT)
        print(f"health_score: Would link {linkable} of {eligible} unlinked Whoop workout strain score(s)")
        if eligible - linkable:
            _report_unresolved(db, eligible - linkable)
        print("\nDry run -- no changes made.")
        return linkable

    linked = db.execute(_UPDATE).rowcount  # ty: ignore[unresolved-attribute]
    print(f"health_score: Linked {linked} of {eligible} unlinked Whoop workout strain score(s)")
    if eligible - linked:
        _report_unresolved(db, eligible - linked)
    return linked


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        linked = backfill_whoop_strain(db, dry_run=dry_run)
        if dry_run or not linked:
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
