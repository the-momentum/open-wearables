#!/usr/bin/env python3
"""Split the legacy ``google`` provider into ``health_connect`` and ``google_health``.

``google`` used to cover two unrelated integrations under one slug: Health Connect data
pushed from Android via the mobile SDK, and the Google Health API cloud OAuth flow. They
are separate providers now, so every stored row has to pick a side.

The discriminator is ``data_source.source``: the Health API stamps the ``google_health_api``
constant on every write path (rollUp, list and reconcile alike), so anything else under
``provider='google'`` came through the SDK importer, which writes the payload's own source
(an app or device name). The cloud rows are claimed by source first and the remainder is SDK
by elimination, so a future Health API source string can never land on the SDK side unnoticed.

The other tables have no per-row discriminator, but only the cloud path ever wrote them:
connections were OAuth-only, and sync runs, settings and priorities are cloud concerns. They
all move to ``google_health``. ``health_score`` follows its data source.

Runs before ``init_provider_settings.py`` in ``scripts/start/app.sh`` so the seeder does not
create the row this rename targets. That ordering is not enough on its own: a pod still on the
old code re-creates legacy rows after the split has run, so every statement also tolerates
finding both spellings already present. Where the two collide on a unique constraint the
canonical row wins and the legacy one is dropped, except in ``data_source`` and
``health_score``, where it holds data and is left in place and reported instead.

Idempotent: every statement is keyed on ``provider = 'google'``, so re-runs are no-ops once
no legacy rows remain. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/split_google_provider.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/split_google_provider.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal

LEGACY = "google"
API = "google_health"
SDK = "health_connect"
API_SOURCE = "google_health_api"

_PARAMS = {"legacy": LEGACY, "api": API, "sdk": SDK, "api_source": API_SOURCE}

_COUNTS: dict[str, TextClause] = {
    "data_source_api": text("SELECT COUNT(*) FROM data_source WHERE provider = :legacy AND source = :api_source"),
    "data_source_sdk": text(
        "SELECT COUNT(*) FROM data_source WHERE provider = :legacy AND source IS DISTINCT FROM :api_source"
    ),
    "health_score": text("SELECT COUNT(*) FROM health_score WHERE provider = :legacy"),
    "user_connection": text("SELECT COUNT(*) FROM user_connection WHERE provider = :legacy"),
    "sync_run": text("SELECT COUNT(*) FROM sync_run WHERE provider = :legacy"),
    "provider_settings": text("SELECT COUNT(*) FROM provider_settings WHERE provider = :legacy"),
    "provider_priority": text("SELECT COUNT(*) FROM provider_priority WHERE provider = :legacy"),
}

# Order matters: the cloud rows are claimed by source before the catch-all. Both skip a row
# whose identity already exists under the target provider — unique on
# (user_id, provider, coalesce(device_model,''), coalesce(source,'')).
_DS_NO_TWIN = """
      AND NOT EXISTS (
          SELECT 1 FROM data_source t
          WHERE t.user_id = ds.user_id
            AND t.provider = {target}
            AND COALESCE(t.device_model, '') = COALESCE(ds.device_model, '')
            AND COALESCE(t.source, '') = COALESCE(ds.source, '')
      )
"""

_DS_API_UPDATE = text(
    "UPDATE data_source ds SET provider = :api WHERE ds.provider = :legacy AND ds.source = :api_source"
    + _DS_NO_TWIN.format(target=":api")
)
_DS_SDK_UPDATE = text(
    "UPDATE data_source ds SET provider = :sdk WHERE ds.provider = :legacy" + _DS_NO_TWIN.format(target=":sdk")
)

# health_score has no source of its own; it inherits whatever its data source just became.
# Rows with no data_source_id can only have come from the cloud path, its only writer.
_HS_UPDATE_FROM_SOURCE = text("""
    UPDATE health_score hs
    SET provider = ds.provider
    FROM data_source ds
    WHERE ds.id = hs.data_source_id
      AND hs.provider = :legacy
      AND ds.provider IN (:api, :sdk)
""")
_HS_UPDATE_ORPHANS = text("""
    UPDATE health_score hs
    SET provider = :api
    WHERE hs.provider = :legacy
      AND NOT EXISTS (
          SELECT 1 FROM health_score t
          WHERE t.user_id = hs.user_id
            AND t.provider = :api
            AND t.category = hs.category
            AND t.recorded_at = hs.recorded_at
      )
""")

_SR_UPDATE = text("UPDATE sync_run SET provider = :api WHERE provider = :legacy")

# provider is the primary key here and unique in provider_priority, so a legacy row cannot be
# renamed on top of a canonical one. The canonical row is the configured one post-split; the
# legacy row only reappears when an old pod re-seeds it, so it is the one that goes.
_PS_DROP_SUPERSEDED = text("""
    DELETE FROM provider_settings
    WHERE provider = :legacy
      AND EXISTS (SELECT 1 FROM provider_settings t WHERE t.provider = :api)
""")
_PS_UPDATE = text("UPDATE provider_settings SET provider = :api WHERE provider = :legacy")

_PP_DROP_SUPERSEDED = text("""
    DELETE FROM provider_priority
    WHERE provider = :legacy
      AND EXISTS (SELECT 1 FROM provider_priority t WHERE t.provider = :api)
""")

# user_connection is unique on (user_id, provider); a collision means the user was already
# split, so those rows are left behind and reported rather than failing the run.
_UC_UPDATE = text("""
    UPDATE user_connection uc
    SET provider = :api
    WHERE uc.provider = :legacy
      AND NOT EXISTS (
          SELECT 1 FROM user_connection e WHERE e.user_id = uc.user_id AND e.provider = :api
      )
""")

# The legacy ranking covered both channels, so health_connect inherits the same number
# instead of falling back to a lazily-created default on its first ingestion.
_PP_CLONE_FOR_SDK = text("""
    INSERT INTO provider_priority (id, provider, priority, created_at, updated_at)
    SELECT gen_random_uuid(), CAST(:sdk AS VARCHAR), priority, now(), now()
    FROM provider_priority
    WHERE provider = :legacy
      AND NOT EXISTS (SELECT 1 FROM provider_priority WHERE provider = :sdk)
""")
_PP_UPDATE = text("UPDATE provider_priority SET provider = :api WHERE provider = :legacy")


def _rowcount(db: Session, query: TextClause) -> int:
    return db.execute(query, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]


def split_google_provider(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Repoint every ``google`` row at one of the two new providers.

    Does not commit — the caller owns the transaction. In dry-run mode counts come from
    up-front SELECTs; in live mode they are the rowcounts actually written.
    """
    if dry_run:
        result = {name: db.execute(query, _PARAMS).scalar() or 0 for name, query in _COUNTS.items()}
        for table, count in result.items():
            print(f"{table:<20} would move {count} row(s)")
        print("\nDry run — no changes made.")
        return result

    data_source_api = _rowcount(db, _DS_API_UPDATE)
    data_source_sdk = _rowcount(db, _DS_SDK_UPDATE)
    health_score = _rowcount(db, _HS_UPDATE_FROM_SOURCE) + _rowcount(db, _HS_UPDATE_ORPHANS)
    user_connection = _rowcount(db, _UC_UPDATE)
    sync_run = _rowcount(db, _SR_UPDATE)

    provider_settings = _rowcount(db, _PS_DROP_SUPERSEDED) + _rowcount(db, _PS_UPDATE)

    _rowcount(db, _PP_CLONE_FOR_SDK)  # must copy the legacy ranking before it is renamed
    provider_priority = _rowcount(db, _PP_DROP_SUPERSEDED) + _rowcount(db, _PP_UPDATE)

    result = {
        "data_source_api": data_source_api,
        "data_source_sdk": data_source_sdk,
        "health_score": health_score,
        "user_connection": user_connection,
        "sync_run": sync_run,
        "provider_settings": provider_settings,
        "provider_priority": provider_priority,
    }
    for table, count in result.items():
        print(f"{table:<20} moved {count} row(s)")

    for table in ("user_connection", "data_source_api", "data_source_sdk", "health_score"):
        stranded = db.execute(_COUNTS[table], _PARAMS).scalar() or 0
        if stranded:
            print(f"\n⚠ {table}: {stranded} row(s) still on '{LEGACY}' — an identical row already exists post-split.")

    return result


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        result = split_google_provider(db, dry_run=dry_run)
        if dry_run:
            return
        if not any(result.values()):
            print(f"Nothing to do — no '{LEGACY}' rows found.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
