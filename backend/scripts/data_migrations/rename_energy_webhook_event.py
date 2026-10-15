#!/usr/bin/env python3
"""Move webhook subscriptions from `series.energy.created` to `series.active_energy.created`.

The series was renamed to active_energy (#1598). A Svix endpoint filters on event-type names,
so switching the name we dispatch would leave every existing subscription intact but matching
a name nothing sends any more — no error, no warning, just silence. Endpoints keep working for
their other filters, which makes the gap even easier to miss.

Run in two phases around the deploy, so no window exists where the dispatched name is absent
from a subscriber's filter:

    1. --phase=add     BEFORE deploying the rename. Appends the new name next to the old one.
    2. deploy          Dispatch switches to the new name; it matches the appended entry.
    3. --phase=remove  AFTER the deploy. Drops the now-dead old name.

Never dispatch both names: between phase 1 and 3 endpoints carry both filters, so two messages
would both match and every subscriber would get a duplicate.

Endpoints with no filter_types receive every event and are left alone. Idempotent: an endpoint
already holding the target state is skipped without a write, so a re-run is a no-op.

Scale: one list call per developer plus one patch per affected endpoint — not per subscription
and not per event. Svix rate limits are the bottleneck, so --sleep throttles between writes.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/rename_energy_webhook_event.py --phase=add --dry-run
    docker compose exec app uv run python scripts/data_migrations/rename_energy_webhook_event.py --phase=add
    docker compose exec app uv run python scripts/data_migrations/rename_energy_webhook_event.py --phase=remove
"""

import argparse
import sys
import time
from collections.abc import Iterator

from app.database import SessionLocal
from app.models import Developer
from app.services.outgoing_webhooks import svix

OLD_EVENT = "series.energy.created"
NEW_EVENT = "series.active_energy.created"


def _target_filters(current: list[str], phase: str) -> list[str] | None:
    """The filter list this endpoint should end up with, or None when it is already correct.

    An endpoint with no filters receives every event and needs no migration, which is why an
    empty result reads as "leave alone" rather than "clear the filters".
    """
    if OLD_EVENT not in current:
        return None
    if phase == "add":
        return None if NEW_EVENT in current else [*current, NEW_EVENT]
    return [f for f in current if f != OLD_EVENT] or None


def _iter_endpoints(app_id: str) -> Iterator:
    """Every endpoint of an application, following Svix's pagination."""
    iterator = None
    while True:
        page = svix.list_endpoints(app_id, iterator=iterator)
        yield from page.data
        if page.done or not page.iterator:
            return
        iterator = page.iterator


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
            endpoints = list(_iter_endpoints(app_id))
        except Exception as exc:  # noqa: BLE001 - a missing app must not abort the run
            print(f"  ! {app_id}: cannot list endpoints ({exc})")
            failed += 1
            continue

        for ep in endpoints:
            scanned += 1
            current = list(ep.event_types or [])
            target = _target_filters(current, phase)
            if target is None:
                if phase == "remove" and current == [OLD_EVENT]:
                    skipped_last_filter += 1
                    print(f"  ! {app_id}/{ep.id}: only filter is {OLD_EVENT}, leaving it (would become a firehose)")
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
