#!/usr/bin/env python3
"""Fix Apple HealthKit walking metrics stored in wrong units.

HealthKit returns walking percentages as a 0-1 fraction (using HKUnit.percent())
and walking_step_length in meters, but the DB unit column says "percent" / "cm".
This script multiplies all affected values by 100 to correct the stored data.

Affected series types:
  - walking_double_support_percentage  (issue #1105)
  - walking_asymmetry_percentage
  - walking_steadiness
  - walking_step_length                (issue #1106)

The filter on each UPDATE is intentionally narrow so the script is safe to re-run
after the ingestion fix is deployed (new rows will already be in the correct range).

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/normalize_apple_walking_metrics.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/normalize_apple_walking_metrics.py
"""

import argparse

from sqlalchemy import TextClause, text

from app.database import SessionLocal

# (series_type_code, value_filter, description)
# value_filter keeps the UPDATE idempotent once the ingestion fix is live:
#   - fractions are < 1; corrected percent values are 0–100
#   - meters are < 10; corrected cm values are 30–150
MIGRATIONS = [
    ("walking_double_support_percentage", "dps.value < 1", "0-1 fraction → percent"),
    ("walking_asymmetry_percentage", "dps.value < 1", "0-1 fraction → percent"),
    ("walking_steadiness", "dps.value < 1", "0-1 fraction → percent"),
    ("walking_step_length", "dps.value < 10", "meters → cm"),
]


def _count_query(value_filter: str) -> TextClause:
    return text(f"""
        SELECT COUNT(*)
        FROM data_point_series dps
        JOIN series_type_definition std ON std.id = dps.series_type_definition_id
        JOIN data_source ds ON ds.id = dps.data_source_id
        WHERE std.code = :code
          AND ds.provider = 'apple'
          AND {value_filter}
    """)  # noqa: S608


def _sample_query(value_filter: str) -> TextClause:
    return text(f"""
        SELECT dps.id, dps.value, dps.value * 100 AS corrected, ds.provider, dps.recorded_at
        FROM data_point_series dps
        JOIN series_type_definition std ON std.id = dps.series_type_definition_id
        JOIN data_source ds ON ds.id = dps.data_source_id
        WHERE std.code = :code
          AND ds.provider = 'apple'
          AND {value_filter}
        ORDER BY dps.recorded_at DESC
        LIMIT 10
    """)  # noqa: S608


def _update_query(value_filter: str) -> TextClause:
    return text(f"""
        UPDATE data_point_series dps
        SET value = dps.value * 100
        FROM series_type_definition std, data_source ds
        WHERE std.id = dps.series_type_definition_id
          AND ds.id = dps.data_source_id
          AND std.code = :code
          AND ds.provider = 'apple'
          AND {value_filter}
    """)  # noqa: S608


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        any_affected = False

        for code, value_filter, description in MIGRATIONS:
            count = db.execute(_count_query(value_filter), {"code": code}).scalar()
            if count == 0:
                print(f"{code}: no affected rows — skipping.")
                continue

            any_affected = True
            print(f"\n{code} ({description}): {count} row(s) to fix")

            rows = db.execute(_sample_query(value_filter), {"code": code}).fetchall()
            print(f"  {'ID':<38} {'Provider':<12} {'Current':>10} {'Corrected':>10}  Recorded at")
            print("  " + "-" * 90)
            for row in rows:
                print(
                    f"  {row.id!s:<38} {row.provider:<12} {row.value:>10.4f} {row.corrected:>10.4f}  {row.recorded_at}"
                )
            if count > 10:
                print(f"  ... and {count - 10} more")

            if not dry_run:
                result = db.execute(_update_query(value_filter), {"code": code})
                print(f"  Updated {result.rowcount} row(s).")

        if not any_affected:
            print("No affected rows across all metrics — nothing to do.")
            return

        if dry_run:
            print("\nDry run — no changes made.")
            return

        db.commit()
        print("\nAll updates committed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without updating")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
