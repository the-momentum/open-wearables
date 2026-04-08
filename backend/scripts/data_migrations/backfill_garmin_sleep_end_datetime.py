#!/usr/bin/env python3
"""Backfill Garmin sleep end_datetime from sleep stage timeline.

Garmin's durationInSeconds only covers asleep time (deep+light+rem),
which caused end_datetime to be earlier than the actual session end.
This script recomputes end_datetime and duration_seconds from the last
stage in the sleep_stages JSONB column.

Reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD from environment
(defaults match the local Docker Compose setup).

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_garmin_sleep_end_datetime.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_garmin_sleep_end_datetime.py
"""

import argparse
import os
import sys

import psycopg

PREVIEW_QUERY = """
    SELECT
        er.id,
        er.start_datetime,
        er.end_datetime AS current_end,
        er.duration_seconds AS current_duration,
        sub.stage_end AS new_end,
        EXTRACT(EPOCH FROM (sub.stage_end - er.start_datetime))::int AS new_duration
    FROM event_record er
    JOIN (
        SELECT
            valid.record_id,
            MAX((stage->>'end_time')::timestamptz) AS stage_end
        FROM (
            SELECT sd.record_id, sd.sleep_stages
            FROM sleep_details sd
            JOIN event_record e ON e.id = sd.record_id
            WHERE sd.sleep_stages IS NOT NULL
              AND jsonb_typeof(sd.sleep_stages) = 'array'
              AND jsonb_array_length(sd.sleep_stages) > 0
              AND e.source_name = 'Garmin'
              AND e.category = 'sleep'
        ) valid
        CROSS JOIN LATERAL jsonb_array_elements(valid.sleep_stages) AS stage
        GROUP BY valid.record_id
    ) sub ON er.id = sub.record_id
    WHERE sub.stage_end > er.end_datetime
    ORDER BY er.start_datetime
"""

UPDATE_QUERY = """
    UPDATE event_record er
    SET
        end_datetime = sub.stage_end,
        duration_seconds = EXTRACT(EPOCH FROM (sub.stage_end - er.start_datetime))::int
    FROM (
        SELECT
            valid.record_id,
            MAX((stage->>'end_time')::timestamptz) AS stage_end
        FROM (
            SELECT sd.record_id, sd.sleep_stages
            FROM sleep_details sd
            JOIN event_record e ON e.id = sd.record_id
            WHERE sd.sleep_stages IS NOT NULL
              AND jsonb_typeof(sd.sleep_stages) = 'array'
              AND jsonb_array_length(sd.sleep_stages) > 0
              AND e.source_name = 'Garmin'
              AND e.category = 'sleep'
        ) valid
        CROSS JOIN LATERAL jsonb_array_elements(valid.sleep_stages) AS stage
        GROUP BY valid.record_id
    ) sub
    WHERE er.id = sub.record_id
      AND sub.stage_end > er.end_datetime
"""


def get_conninfo() -> str:
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return (
        f"host={os.environ['DB_HOST']} port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Garmin sleep end_datetime from stage timeline.")
    parser.add_argument("--dry-run", action="store_true", help="Preview affected records without making changes.")
    args = parser.parse_args()

    with psycopg.connect(get_conninfo()) as conn, conn.cursor() as cur:
        if args.dry_run:
            cur.execute(PREVIEW_QUERY)
            rows = cur.fetchall()

            if not rows:
                print("No records to update.")
                return

            print(f"{'ID':<38} {'Start':<22} {'Current End':<22} {'New End':<22} {'Diff (min)':<10}")
            print("-" * 114)
            for row in rows:
                record_id, start, current_end, current_dur, new_end, new_dur = row
                diff_min = (new_dur - (current_dur or 0)) // 60
                print(f"{record_id}   {start!s:<22} {current_end!s:<22} {new_end!s:<22} {diff_min:>+8}")

            print(f"\nTotal: {len(rows)} record(s) to update.")
            print("\nDry run - no changes made.")
            return

        cur.execute(UPDATE_QUERY)
        conn.commit()
        print(f"Updated {cur.rowcount} record(s).")


if __name__ == "__main__":
    main()
