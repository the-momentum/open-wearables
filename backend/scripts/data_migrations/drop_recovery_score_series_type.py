#!/usr/bin/env python3
"""Remove recovery_score timeseries data from the database.

Recovery score is now stored in the health_score table for all providers
(Whoop, Oura, Suunto). This script deletes the legacy data_point_series
rows and the series_type_definition row (id=6, code='recovery_score').

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/drop_recovery_score_series_type.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/drop_recovery_score_series_type.py
"""

import argparse
import sys

from sqlalchemy import text

from app.database import SessionLocal

SERIES_TYPE_ID = 6
SERIES_TYPE_CODE = "recovery_score"


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        row_count = db.execute(
            text("SELECT COUNT(*) FROM data_point_series WHERE series_type_definition_id = :id"),
            {"id": SERIES_TYPE_ID},
        ).scalar()
        archive_count = db.execute(
            text("SELECT COUNT(*) FROM data_point_series_archive WHERE series_type_definition_id = :id"),
            {"id": SERIES_TYPE_ID},
        ).scalar()

        print(f"data_point_series rows to delete:         {row_count}")
        print(f"data_point_series_archive rows to delete: {archive_count}")

        if dry_run:
            print("Dry run — no changes made.")
            return

        db.execute(
            text("DELETE FROM data_point_series WHERE series_type_definition_id = :id"),
            {"id": SERIES_TYPE_ID},
        )
        db.execute(
            text("DELETE FROM data_point_series_archive WHERE series_type_definition_id = :id"),
            {"id": SERIES_TYPE_ID},
        )
        db.execute(
            text("DELETE FROM series_type_definition WHERE id = :id AND code = :code"),
            {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE},
        )
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without deleting")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
    sys.exit(0)
