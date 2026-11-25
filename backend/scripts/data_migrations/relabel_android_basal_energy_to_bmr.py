#!/usr/bin/env python3
"""Relabel Android basal_energy rows to the basal_metabolic_rate series.

Health Connect's BasalMetabolicRateRecord (and the Samsung Health Data SDK equivalent)
is a kcal/day rate estimate, not energy burned over an interval, but the ingestion
historically stored it under basal_energy (id=82). On the Android SDK providers no
other record type writes basal_energy — Apple's genuine interval basal energy comes
from HKQuantityTypeIdentifierBasalEnergyBurned on provider='apple' — so every
health_connect/samsung basal_energy row is a BMR reading. The ingestion path now writes
the dedicated basal_metabolic_rate series (id=90); this script corrects pre-existing
rows in series_sample and data_point_series_archive.

Relabeled rows also get is_daily_total=NULL: a BMR reading is an instantaneous rate,
and the new series is AVG-aggregated, where the flag does not apply.

Conflict handling: after the ingestion fix, a re-sync can write a correct
basal_metabolic_rate row at the same (data_source, recorded_at) as an old basal_energy
row, which would collide with the unique constraint on relabel. In that case the stale
basal_energy duplicate is deleted rather than relabeled.

Idempotent: once relabeled, rows no longer match the basal_energy filter, so re-runs
are no-ops. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/relabel_android_basal_energy_to_bmr.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/relabel_android_basal_energy_to_bmr.py
"""

import argparse

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

PROVIDERS = ("health_connect", "samsung")
BASAL_ENERGY_ID = 82
BMR_ID = 90

_PARAMS = {"providers": list(PROVIDERS), "basal": BASAL_ENERGY_ID, "bmr": BMR_ID}


def _q(sql: str) -> TextClause:
    return text(sql).bindparams(bindparam("providers", expanding=True))


# series_sample: unique on (data_source_id, series_type_definition_id, recorded_at)
_SERIES_COUNT = _q("""
    SELECT COUNT(*)
    FROM series_sample dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
""")

# basal_energy rows that collide with an already-correct basal_metabolic_rate row —
# these get deleted, not relabeled.
_SERIES_CONFLICT_COUNT = _q("""
    SELECT COUNT(*)
    FROM series_sample dps
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

_SERIES_UPDATE = _q("""
    UPDATE series_sample dps
    SET series_type_definition_id = :bmr, is_daily_total = NULL
    FROM data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND NOT EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

# Any basal_energy Android rows still present collided with an existing
# basal_metabolic_rate row above. The EXISTS guard ensures we only delete confirmed
# duplicates — rows without a counterpart (e.g. written by an old pod during a rolling
# deploy) are left for the next startup run to pick up via _SERIES_UPDATE.
_SERIES_DELETE_DUPLICATES = _q("""
    DELETE FROM series_sample dps
    USING data_source ds
    WHERE ds.id = dps.data_source_id
      AND ds.provider IN :providers
      AND dps.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM series_sample e
          WHERE e.data_source_id = dps.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.recorded_at = dps.recorded_at
      )
""")

# data_point_series_archive: unique on (data_source_id, series_type_definition_id,
# bucket_start_at, aggregation_type)
_ARCHIVE_COUNT = _q("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider IN :providers
      AND a.series_type_definition_id = :basal
""")

# basal_energy is a SUM series, so its archived buckets are sums of rate samples, while
# basal_metabolic_rate is read through its canonical AVG row. sum/sample_count is exactly
# the mean the archiver would have written, so conversion preserves the information; every
# relabeled bucket lands as an 'avg' row, which is also what the conflict checks key on.
_ARCHIVE_CONFLICT_COUNT = _q("""
    SELECT COUNT(*)
    FROM data_point_series_archive a
    JOIN data_source ds ON ds.id = a.data_source_id
    WHERE ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = 'avg'
      )
""")

_ARCHIVE_UPDATE = _q("""
    UPDATE data_point_series_archive a
    SET series_type_definition_id = :bmr,
        value = CASE WHEN a.aggregation_type = 'sum' THEN a.value / GREATEST(a.sample_count, 1) ELSE a.value END,
        aggregation_type = 'avg'
    FROM data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND NOT EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = 'avg'
      )
""")

_ARCHIVE_DELETE_DUPLICATES = _q("""
    DELETE FROM data_point_series_archive a
    USING data_source ds
    WHERE ds.id = a.data_source_id
      AND ds.provider IN :providers
      AND a.series_type_definition_id = :basal
      AND EXISTS (
          SELECT 1 FROM data_point_series_archive e
          WHERE e.data_source_id = a.data_source_id
            AND e.series_type_definition_id = :bmr
            AND e.bucket_start_at = a.bucket_start_at
            AND e.aggregation_type = 'avg'
      )
""")

# data_type_coverage keyed (user, provider, 'basal_energy', series) describes only BMR
# data on the Android providers, so it re-keys to basal_metabolic_rate with the rows.
# The narrowing advisory lock matches DataTypeCoverageRepository, so a concurrent
# coverage backfill cannot re-widen the old key after the move.
_COVERAGE_ADVISORY_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended('data_type_coverage:narrowing', 0))")

# Row-lock every coverage key this migration touches before re-keying, in the same
# canonical order the write paths widen them, so a concurrent writer's widening UPDATE
# blocks until this transaction commits instead of interleaving: without it the span
# recompute below can read a snapshot that excludes a writer's uncommitted sample and
# then overwrite that writer's wider span when the row lock unblocks. Taken after the
# row relabel so the locks are only held for the short coverage section.
_COVERAGE_ROW_LOCK = _q("""
    SELECT user_id, provider, data_type FROM data_type_coverage
    WHERE provider IN :providers AND kind = 'series'
      AND data_type IN ('basal_energy', 'basal_metabolic_rate')
    ORDER BY user_id, provider, data_type
    FOR UPDATE
""")

# The same three-step re-key merge_average_met_into_physical_effort uses: widen an existing
# basal_metabolic_rate span with the basal_energy one, drop the merged old rows, then rename
# whatever old rows have no counterpart. Scoped to the Android providers, so Apple's genuine
# basal_energy coverage is left alone. Unconditional: most basal_energy rows are already
# relabeled at this point and their span belongs under the new key no matter what happens
# to stragglers.
_COVERAGE_MOVE = [
    _q("""
        UPDATE data_type_coverage n SET
            coverage_start = LEAST(n.coverage_start, o.coverage_start),
            coverage_end = GREATEST(n.coverage_end, o.coverage_end),
            last_written_at = GREATEST(n.last_written_at, o.last_written_at)
        FROM data_type_coverage o
        WHERE o.user_id = n.user_id AND o.provider = n.provider AND o.kind = n.kind
          AND o.provider IN :providers AND o.kind = 'series'
          AND o.data_type = 'basal_energy' AND n.data_type = 'basal_metabolic_rate'
    """),
    _q("""
        DELETE FROM data_type_coverage o
        WHERE o.provider IN :providers AND o.kind = 'series' AND o.data_type = 'basal_energy'
          AND EXISTS (
            SELECT 1 FROM data_type_coverage n
            WHERE n.user_id = o.user_id AND n.provider = o.provider AND n.kind = o.kind
              AND n.data_type = 'basal_metabolic_rate'
          )
    """),
    _q("""
        UPDATE data_type_coverage o SET data_type = 'basal_metabolic_rate'
        WHERE o.provider IN :providers AND o.kind = 'series' AND o.data_type = 'basal_energy'
    """),
]

# Rolling-deploy repair: under READ COMMITTED each statement reads a fresh snapshot, so a
# pod on the previous release can commit a basal_energy row after the relabel UPDATE above
# but before the coverage re-key. The re-key then moves the coverage the write path wrote
# for it, leaving the surviving row with no basal_energy span at all. Re-create one keyed
# exactly to what survived: the write paths widen it from there. Runs in the same
# transaction, so the keys always describe the rows they cover once this commits; the
# startup rerun relabels the straggler itself once the rollout ends.
# last_written_at mirrors the coverage backfill and uses the sample time: a write arrives
# no earlier than its samples, so on conflict GREATEST always keeps the writer's own
# arrival time where its row survived, and the approximation only applies to a fresh
# insert, where the true arrival time was carried away with the re-keyed row.
_COVERAGE_REPAIR = _q("""
    INSERT INTO data_type_coverage (user_id, provider, data_type, kind, coverage_start, coverage_end, last_written_at)
    SELECT user_id, provider, data_type, kind, coverage_start, coverage_end, coverage_end
    FROM (
        SELECT ds.user_id, ds.provider, 'basal_energy' AS data_type, 'series' AS kind,
               MIN(s.recorded_at) AS coverage_start, MAX(s.recorded_at) AS coverage_end
        FROM series_sample s
        JOIN data_source ds ON ds.id = s.data_source_id
        WHERE ds.provider IN :providers
          AND s.series_type_definition_id = :basal
        GROUP BY ds.user_id, ds.provider
    ) spans
    ON CONFLICT (user_id, provider, data_type, kind) DO UPDATE SET
        coverage_start = LEAST(EXCLUDED.coverage_start, data_type_coverage.coverage_start),
        coverage_end = GREATEST(EXCLUDED.coverage_end, data_type_coverage.coverage_end),
        last_written_at = GREATEST(EXCLUDED.last_written_at, data_type_coverage.last_written_at)
""")

# The re-keyed basal_metabolic_rate span is the old basal_energy envelope, which the write
# path may have widened for a straggler that is not in the BMR series. Recompute it from the
# rows actually held — live and archived, the same sources DataTypeCoverageRepository's own
# backfill derives spans from — so both keys exactly envelope their rows.
_BMR_SPAN_RECOMPUTE = _q("""
    UPDATE data_type_coverage c SET
        coverage_start = spans.coverage_start,
        coverage_end = spans.coverage_end
    FROM (
        SELECT user_id, provider, MIN(ts) AS coverage_start, MAX(ts) AS coverage_end
        FROM (
            SELECT ds.user_id, ds.provider, s.recorded_at AS ts
            FROM series_sample s
            JOIN data_source ds ON ds.id = s.data_source_id
            WHERE ds.provider IN :providers AND s.series_type_definition_id = :bmr
            UNION ALL
            SELECT ds.user_id, ds.provider, a.bucket_start_at
            FROM data_point_series_archive a
            JOIN data_source ds ON ds.id = a.data_source_id
            WHERE ds.provider IN :providers AND a.series_type_definition_id = :bmr
        ) rows_held
        GROUP BY user_id, provider
    ) spans
    WHERE c.user_id = spans.user_id AND c.provider = spans.provider
      AND c.kind = 'series' AND c.data_type = 'basal_metabolic_rate'
""")

_COVERAGE_COUNT = _q("""
    SELECT COUNT(*) FROM data_type_coverage
    WHERE provider IN :providers AND data_type = 'basal_energy' AND kind = 'series'
""")


def _scalar_count(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).scalar() or 0


def _relabel_rows(db: Session) -> tuple[int, int, int, int]:
    """Move Android basal_energy rows in series_sample and the archive to the BMR series."""
    series_updated = db.execute(_SERIES_UPDATE, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    series_deleted = db.execute(_SERIES_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    archive_updated = db.execute(_ARCHIVE_UPDATE, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    archive_deleted = db.execute(_ARCHIVE_DELETE_DUPLICATES, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    return series_updated, series_deleted, archive_updated, archive_deleted


def _rekey_coverage(db: Session) -> tuple[int, int]:
    """Re-key basal_energy coverage spans to basal_metabolic_rate, then repair the key of
    any basal_energy rows that survived the relabel (a rolling-deploy write can land one
    between the two steps — split out so tests can interleave one)."""
    db.execute(_COVERAGE_ADVISORY_LOCK)
    db.execute(_COVERAGE_ROW_LOCK, _PARAMS)
    moved = 0
    for statement in _COVERAGE_MOVE:
        moved += db.execute(statement, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    repaired = db.execute(_COVERAGE_REPAIR, _PARAMS).rowcount  # ty: ignore[missing-attribute]
    db.execute(_BMR_SPAN_RECOMPUTE, _PARAMS)
    return moved, repaired


def relabel_android_basal_energy(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Relabel Android basal_energy rows to basal_metabolic_rate. Does not commit —
    caller owns the transaction.

    In dry-run mode counts come from up-front SELECTs. In live mode counts come from
    the actual rowcount returned by each DML statement, so reported numbers reflect
    what was truly written. Rows that collide with an already-correct
    basal_metabolic_rate row are deleted rather than relabeled.
    """
    if dry_run:
        series_deleted = _scalar_count(db, _SERIES_CONFLICT_COUNT)
        series_updated = _scalar_count(db, _SERIES_COUNT) - series_deleted
        archive_deleted = _scalar_count(db, _ARCHIVE_CONFLICT_COUNT)
        archive_updated = _scalar_count(db, _ARCHIVE_COUNT) - archive_deleted
        coverage_moved = _scalar_count(db, _COVERAGE_COUNT)
        print(f"series_sample:         Would relabel {series_updated}, remove {series_deleted} duplicate(s)")
        print(f"data_point_series_archive: Would relabel {archive_updated}, remove {archive_deleted} duplicate(s)")
        print(f"data_type_coverage:    Would re-key {coverage_moved} span(s) to basal_metabolic_rate")
        print("\nDry run — no changes made.")
        return {
            "series_updated": series_updated,
            "series_deleted": series_deleted,
            "archive_updated": archive_updated,
            "archive_deleted": archive_deleted,
            "coverage_moved": coverage_moved,
        }

    series_updated, series_deleted, archive_updated, archive_deleted = _relabel_rows(db)
    coverage_moved, coverage_repaired = _rekey_coverage(db)

    print(f"series_sample:         Relabeled {series_updated}, removed {series_deleted} duplicate(s)")
    print(f"data_point_series_archive: Relabeled {archive_updated}, removed {archive_deleted} duplicate(s)")
    print(
        f"data_type_coverage:    Re-keyed {coverage_moved} span(s) to basal_metabolic_rate,"
        f" repaired {coverage_repaired} rolling-deploy span(s)"
    )

    return {
        "series_updated": series_updated,
        "series_deleted": series_deleted,
        "archive_updated": archive_updated,
        "archive_deleted": archive_deleted,
        "coverage_moved": coverage_moved,
    }


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = relabel_android_basal_energy(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print("Nothing to do — no Android basal_energy rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
