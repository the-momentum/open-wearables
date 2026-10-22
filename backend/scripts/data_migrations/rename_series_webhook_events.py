#!/usr/bin/env python3
"""Move webhook subscriptions off the series event types the granularity stack renames or retires.

- `series.walking_heart_rate_average.created` -> `series.walking_heart_rate.created` (the series was renamed)
- `series.average_met.created` -> retired: average_met merged into physical_effort, and a workout's
  average MET is a session value now, not a sample, so no series event carries it any more

A Svix endpoint filters on event-type names, so switching the name we dispatch would leave every
existing subscription intact but matching a name nothing sends any more: no error, just silence.

Run in two phases around the deploy, so no window exists where the dispatched name is absent
from a subscriber's filter:

    1. --phase=add     BEFORE deploying. Appends each new name next to its old one.
    2. deploy          Dispatch switches to the new names; they match the appended entries.
    3. --phase=remove  AFTER the deploy. Drops the now-dead old names, retired ones included.

Endpoints with no filter_types receive every event and are left alone, as is an endpoint whose only
filters are old names (dropping them would widen it to every event). Idempotent: an endpoint already
holding the target state is skipped without a write, so a re-run is a no-op.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/rename_series_webhook_events.py --phase=add --dry-run
    docker compose exec app uv run python scripts/data_migrations/rename_series_webhook_events.py --phase=add
    docker compose exec app uv run python scripts/data_migrations/rename_series_webhook_events.py --phase=remove
"""

import argparse
import sys
import time

from app.database import SessionLocal
from app.models import Developer
from app.services.outgoing_webhooks import svix

# Old event type -> its new name, or None where the event is retired.
RENAMED: dict[str, str | None] = {
    "series.walking_heart_rate_average.created": "series.walking_heart_rate.created",
    "series.average_met.created": None,
}


def _target_filters(current: list[str], phase: str) -> list[str] | None:
    """The filter list this endpoint should end up with, or None when it is already correct.

    An endpoint with no filters receives every event and needs no migration, which is why an
    empty result reads as "leave alone" rather than "clear the filters".
    """
    if phase == "add":
        added = [new for old, new in RENAMED.items() if old in current and new and new not in current]
        return [*current, *added] if added else None
    kept = [f for f in current if f not in RENAMED]
    return kept if kept and kept != current else None


def main(phase: str, dry_run: bool, sleep: float) -> int:
    if not svix.is_enabled():
        print("Svix is disabled — nothing to migrate.")
        return 0

    with SessionLocal() as db:
        developer_ids = [str(d.id) for d in db.query(Developer.id).all()]
    print(f"Developers to scan: {len(developer_ids)}")

    scanned = patched = skipped_last_filter = failed = 0
    for app_id in developer_ids:
        try:
            endpoints = list(svix.iter_endpoints(app_id))
        except Exception as exc:  # noqa: BLE001 - a missing app must not abort the run
            print(f"  ! {app_id}: cannot list endpoints ({exc})")
            failed += 1
            continue

        for ep in endpoints:
            scanned += 1
            current = list(ep.event_types or [])
            target = _target_filters(current, phase)
            if target is None:
                if phase == "remove" and current and set(current) <= set(RENAMED):
                    skipped_last_filter += 1
                    print(f"  ! {app_id}/{ep.id}: only filters are {current}, leaving them (would become a firehose)")
                continue

            print(f"  {'[dry-run] ' if dry_run else ''}{app_id}/{ep.id}: {current} -> {target}")
            if not dry_run:
                # One endpoint the API refuses must not strand the rest half-migrated.
                try:
                    svix.patch_endpoint(app_id, ep.id, filter_types=target)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {app_id}/{ep.id}: patch failed ({exc})")
                    failed += 1
                    continue
                if sleep:
                    time.sleep(sleep)
            patched += 1

    print(f"\nScanned {scanned} endpoints, {'would patch' if dry_run else 'patched'} {patched}.")
    if skipped_last_filter:
        print(f"{skipped_last_filter} endpoint(s) left untouched — remove the filter by hand or widen it first.")
    if failed:
        print(f"{failed} failure(s) — re-run once resolved; the migration is idempotent.")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("add", "remove"), required=True, help="Run before or after the deploy")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--sleep", type=float, default=0.05, help="Seconds between writes (Svix rate limits)")
    args = parser.parse_args()
    sys.exit(main(phase=args.phase, dry_run=args.dry_run, sleep=args.sleep))
