#!/usr/bin/env python3
"""Fix body_fat_percentage values incorrectly stored 100x too large.

Android Health Connect (Samsung, Google) reports body_fat_percentage already in
percent (e.g. 30.4), but the shared ImportService was unconditionally applying a
ratio->percent x100 conversion intended only for Apple HealthKit, producing values
like 3040. PR #917 fixed the ingestion path; this script corrects existing rows.

Only rows with value > 100 are touched — valid body fat percentages are 0–100.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/normalize_body_fat_percentage.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/normalize_body_fat_percentage.py
"""

import argparse

from sqlalchemy import text

from app.database import SessionLocal

SERIES_TYPE_CODE = "body_fat_percentage"

_AFFECTED_COUNT = text("""
    SELECT COUNT(*)
    FROM data_point_series dps
    JOIN series_type_definition std ON std.id = dps.series_type_definition_id
    WHERE std.code = :code
      AND dps.value > 100
""")

_SAMPLE_ROWS = text("""
    SELECT dps.id, dps.value, dps.value / 100 AS corrected, ds.provider, dps.recorded_at
    FROM data_point_series dps
    JOIN series_type_definition std ON std.id = dps.series_type_definition_id
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE std.code = :code
      AND dps.value > 100
    ORDER BY dps.value DESC
    LIMIT 20
""")

_UPDATE = text("""
    UPDATE data_point_series dps
    SET value = dps.value / 100
    FROM series_type_definition std
    WHERE std.id = dps.series_type_definition_id
      AND std.code = :code
      AND dps.value > 100
""")


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        count = db.execute(_AFFECTED_COUNT, {"code": SERIES_TYPE_CODE}).scalar()

        if count == 0:
            print("No affected rows — nothing to do.")
            return

        print(f"Rows with body_fat_percentage > 100: {count}")

        rows = db.execute(_SAMPLE_ROWS, {"code": SERIES_TYPE_CODE}).fetchall()
        print(f"\n{'ID':<38} {'Provider':<12} {'Current':>10} {'Corrected':>10}  Recorded at")
        print("-" * 95)
        for row in rows:
            print(f"{row.id!s:<38} {row.provider:<12} {row.value:>10.3f} {row.corrected:>10.3f}  {row.recorded_at}")
        if count > 20:
            print(f"  ... and {count - 20} more")

        if dry_run:
            print("\nDry run — no changes made.")
            return

        result = db.execute(_UPDATE, {"code": SERIES_TYPE_CODE})
        db.commit()
        print(f"\nUpdated {result.rowcount} row(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without updating")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
