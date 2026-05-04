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

from sqlalchemy import text

from app.database import SessionLocal

SERIES_TYPE_ID = 6
SERIES_TYPE_CODE = "recovery_score"


_GUARD = "SELECT id FROM series_type_definition WHERE id = :id AND code = :code"


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        matched_id = db.execute(text(_GUARD), {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE}).scalar()
        if matched_id is None:
            print(
                f"Nothing to do: series_type_definition row with id={SERIES_TYPE_ID} and "
                f"code='{SERIES_TYPE_CODE}' not found — already deleted or never existed."
            )
            return

        row_count = db.execute(
            text(f"SELECT COUNT(*) FROM data_point_series WHERE series_type_definition_id IN ({_GUARD})"),
            {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE},
        ).scalar()
        archive_count = db.execute(
            text(f"SELECT COUNT(*) FROM data_point_series_archive WHERE series_type_definition_id IN ({_GUARD})"),
            {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE},
        ).scalar()

        print(f"data_point_series rows to delete:         {row_count}")
        print(f"data_point_series_archive rows to delete: {archive_count}")

        if dry_run:
            print("Dry run — no changes made.")
            return

        db.execute(
            text(f"DELETE FROM data_point_series WHERE series_type_definition_id IN ({_GUARD})"),
            {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE},
        )
        db.execute(
            text(f"DELETE FROM data_point_series_archive WHERE series_type_definition_id IN ({_GUARD})"),
            {"id": SERIES_TYPE_ID, "code": SERIES_TYPE_CODE},
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
