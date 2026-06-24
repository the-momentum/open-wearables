#!/usr/bin/env python3
# Backfill data_point_series.is_daily_total for archival (legacy) rows.
#
# Only daily-total rows are set to TRUE. Every other row is left NULL, which the
# aggregation treats as FALSE (intraday / not a daily total). This keeps the
# rewrite to the small minority of daily rows — the bulk of the table (intraday
# samples, e.g. Apple ~86%) is never touched.
#
# SAFETY + IDEMPOTENCY: the script only ever flips NULL -> TRUE. It never touches
# a row whose is_daily_total is already set (TRUE or FALSE). That makes re-runs
# no-ops AND protects rows written by the post-deploy ingestion stamp — notably
# Garmin epochs, which now carry external_id (a slot id) yet are FALSE, so a naive
# "external_id IS NOT NULL -> TRUE" rule would wrongly flip them. Filtering on
# `is_daily_total IS NULL` excludes them.
#
# PERFORMANCE: data_source_id and series ids are resolved up front, so every
# UPDATE filters on (data_source_id, series_type_definition_id) — the leading
# columns of uq_data_point_series_source_type_time — for an index range scan, no
# per-batch JOINs. Work is committed in --batch chunks (no long locks / no single
# giant transaction).
#
# Per-provider rules (only Garmin & Suunto have a daily+intraday overlap):
#   garmin  steps/energy where external_id IS NOT NULL  -> daily total
#           (legacy epochs had NULL external_id, so this cleanly selects dailies)
#   garmin  distance/flights/resting_heart_rate (all)   -> daily (single channel)
#   suunto  steps/energy: per day the max-value row is the daily total; on the
#           first/last day only when max == sum(rest), i.e. value*2 == day_total
#           (avoids labelling a partial boundary day's largest sample as a total)
#   suunto  resting_heart_rate (all)                    -> daily
#   oura    daily_activity/readiness/spo2/personal_info series -> daily
#   polar   activities series (steps/energy/distance)   -> daily
#   whoop   all series (recovery/body, daily cadence)   -> daily
#   apple/google/samsung/ultrahuman: nothing (all intraday -> stay NULL = false)
#
# Usage (inside Docker):
#   docker compose exec app uv run python scripts/data_migrations/backfill_is_daily_total.py --dry-run
#   docker compose exec app uv run python scripts/data_migrations/backfill_is_daily_total.py

import argparse
import os
import sys
from typing import LiteralString

import psycopg
from psycopg.conninfo import make_conninfo

# provider -> (series codes, require external_id NOT NULL)
# Only summable (SUM) series carry is_daily_total — they are the ones the prefer-daily
# aggregation sums. Non-summable series (HR, weight, spo2, vo2, resting_hr, ...) are left
# NULL. So the rules cover steps/energy/distance/flights only.
#
# Garmin: ALL four summable series use require_ext=True. Garmin daily rows carry a
# summaryId (external_id, "x..." prefix); legacy intraday rows from FIT/activity
# uploads (distance/flights on device-model sources) have NULL external_id, so this
# correctly leaves them NULL instead of mislabelling them daily. Verified in DB.
# Oura/Polar daily rows have NO external_id, so they use require_ext=False.
TRUE_RULES: list[tuple[str, list[str], bool]] = [
    ("garmin", ["steps", "energy", "distance_walking_running", "flights_climbed"], True),
    ("oura", ["steps", "energy", "distance_walking_running"], False),
    ("polar", ["steps", "energy", "distance_walking_running"], False),
]

# require_ext is a bound bool param: when False the predicate is a no-op; when True
# it restricts to rows with a non-null external_id (legacy Garmin dailies).
_RULE_PREDICATE = """
    data_source_id = ANY(%(sources)s)
    AND series_type_definition_id = ANY(%(series)s)
    AND is_daily_total IS NULL
    AND (NOT %(require_ext)s OR external_id IS NOT NULL)
"""
RULE_COUNT_SQL = f"SELECT COUNT(*) FROM data_point_series WHERE {_RULE_PREDICATE}"
RULE_UPDATE_SQL = f"""
    WITH batch AS (
        SELECT id FROM data_point_series WHERE {_RULE_PREDICATE} LIMIT %(batch)s
    )
    UPDATE data_point_series d SET is_daily_total = TRUE FROM batch WHERE d.id = batch.id
"""

# Suunto steps/energy daily total = the per-day max-value row. On the first/last
# day of a source's history (possibly partial, maybe missing the daily-stat row)
# only accept it when max == sum(rest), i.e. value*2 == day_total.
_SUUNTO_DAILY_IDS = """
    WITH base AS (
        SELECT
            id,
            value,
            recorded_at::date AS d,
            SUM(value) OVER w AS day_total,
            ROW_NUMBER() OVER (
                PARTITION BY data_source_id, series_type_definition_id, recorded_at::date
                ORDER BY value DESC, recorded_at
            ) AS rn,
            MIN(recorded_at::date) OVER src AS first_d,
            MAX(recorded_at::date) OVER src AS last_d
        FROM data_point_series
        WHERE data_source_id = ANY(%(sources)s) AND series_type_definition_id = ANY(%(series)s)
        WINDOW
            w AS (PARTITION BY data_source_id, series_type_definition_id, recorded_at::date),
            src AS (PARTITION BY data_source_id, series_type_definition_id)
    )
    SELECT id FROM base
    WHERE rn = 1 AND ((d <> first_d AND d <> last_d) OR (value * 2 = day_total))
"""
SUUNTO_COUNT_SQL = f"""
    SELECT COUNT(*) FROM data_point_series
    WHERE id IN ({_SUUNTO_DAILY_IDS}) AND is_daily_total IS NULL
"""
SUUNTO_UPDATE_SQL = f"""
    WITH daily AS ({_SUUNTO_DAILY_IDS}),
         batch AS (
            SELECT id FROM data_point_series
            WHERE id IN (SELECT id FROM daily) AND is_daily_total IS NULL
            LIMIT %(batch)s
         )
    UPDATE data_point_series d SET is_daily_total = TRUE FROM batch WHERE d.id = batch.id
"""


def get_conninfo() -> str:
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return make_conninfo(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def scalar(cur: psycopg.Cursor) -> int:
    row = cur.fetchone()
    return int(row[0]) if row else 0


def resolve_series_ids(cur: psycopg.Cursor, codes: list[str]) -> list[int]:
    cur.execute("SELECT id FROM series_type_definition WHERE code = ANY(%s)", (codes,))
    return [r[0] for r in cur.fetchall()]


def resolve_source_ids(cur: psycopg.Cursor, provider: str) -> list:
    cur.execute("SELECT id FROM data_source WHERE provider = %s", (provider,))
    return [r[0] for r in cur.fetchall()]


def run_batched(
    cur: psycopg.Cursor, conn: psycopg.Connection, update_sql: LiteralString, params: dict, batch: int
) -> int:
    if batch <= 0:
        raise ValueError(f"batch must be a positive integer, got {batch}")
    total = 0
    while True:
        cur.execute(update_sql, {**params, "batch": batch})
        n = cur.rowcount
        conn.commit()
        total += n
        if n < batch:
            return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill data_point_series.is_daily_total (legacy NULL rows -> TRUE)."
    )
    parser.add_argument("--dry-run", action="store_true", help="Count rows that would change; make no changes.")
    parser.add_argument("--batch", type=int, default=50000, help="Rows per UPDATE batch (default 50000).")
    args = parser.parse_args()
    if args.batch <= 0:
        parser.error("--batch must be a positive integer")

    verb = "would set" if args.dry_run else "set"
    with psycopg.connect(get_conninfo()) as conn, conn.cursor() as cur:
        grand = 0
        for provider, codes, require_ext in TRUE_RULES:
            source_ids = resolve_source_ids(cur, provider)
            if not source_ids:
                continue
            params = {"sources": source_ids, "series": resolve_series_ids(cur, codes), "require_ext": require_ext}
            if args.dry_run:
                cur.execute(RULE_COUNT_SQL, params)
                n = scalar(cur)
            else:
                n = run_batched(cur, conn, RULE_UPDATE_SQL, params, args.batch)
            label = f"{provider}:{','.join(codes)}" + (" [external_id]" if require_ext else "")
            print(f"{verb} TRUE  {n:>10}  {label}")
            grand += n

        suunto_sources = resolve_source_ids(cur, "suunto")
        if suunto_sources:
            params = {"sources": suunto_sources, "series": resolve_series_ids(cur, ["steps", "energy"])}
            if args.dry_run:
                cur.execute(SUUNTO_COUNT_SQL, params)
                n = scalar(cur)
            else:
                n = run_batched(cur, conn, SUUNTO_UPDATE_SQL, params, args.batch)
            print(f"{verb} TRUE  {n:>10}  suunto:steps,energy [max/day heuristic]")
            grand += n

        print(
            f"\n{'Would update' if args.dry_run else 'Updated'} {grand} row(s)."
            + (" (dry run)" if args.dry_run else "")
        )


if __name__ == "__main__":
    main()
