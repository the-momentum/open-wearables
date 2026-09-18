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

Connections and sync runs carry their own discriminator: a connection created by an SDK
upload holds no OAuth material at all, and a run records the transport that produced it.
Settings and priorities were only ever a cloud concern, so they move to ``google_health``.
``health_score`` follows its data source.

Runs before ``init_provider_settings.py`` in ``scripts/start/app.sh``: that seeds a
``google_health`` row, and ``provider_settings.provider`` is a primary key, so the rename
would collide with it.

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
from app.schemas.sync_status import SyncSource

LEGACY = "google"
API = "google_health"
SDK = "health_connect"
API_SOURCE = "google_health_api"
SDK_SOURCE = SyncSource.SDK.value

_UC_NO_OAUTH = """
      AND access_token IS NULL
      AND refresh_token IS NULL
      AND provider_user_id IS NULL
      AND scope IS NULL
"""
_UC_HAS_OAUTH = """
      AND (
          access_token IS NOT NULL
          OR refresh_token IS NOT NULL
          OR provider_user_id IS NOT NULL
          OR scope IS NOT NULL
      )
"""

_PARAMS = {"legacy": LEGACY, "api": API, "sdk": SDK, "api_source": API_SOURCE, "sdk_source": SDK_SOURCE}

_COUNTS: dict[str, TextClause] = {
    "data_source_api": text("SELECT COUNT(*) FROM data_source WHERE provider = :legacy AND source = :api_source"),
    "data_source_sdk": text(
        "SELECT COUNT(*) FROM data_source WHERE provider = :legacy AND source IS DISTINCT FROM :api_source"
    ),
    "health_score": text("SELECT COUNT(*) FROM health_score WHERE provider = :legacy"),
    "user_connection_api": text("SELECT COUNT(*) FROM user_connection WHERE provider = :legacy" + _UC_HAS_OAUTH),
    "user_connection_sdk": text("SELECT COUNT(*) FROM user_connection WHERE provider = :legacy" + _UC_NO_OAUTH),
    "sync_run": text("SELECT COUNT(*) FROM sync_run WHERE provider = :legacy"),
    "provider_settings": text("SELECT COUNT(*) FROM provider_settings WHERE provider = :legacy"),
    "provider_priority": text("SELECT COUNT(*) FROM provider_priority WHERE provider = :legacy"),
}

# Order matters: the cloud rows are claimed by source before the catch-all.
_DS_API_UPDATE = text("UPDATE data_source SET provider = :api WHERE provider = :legacy AND source = :api_source")
_DS_SDK_UPDATE = text("UPDATE data_source SET provider = :sdk WHERE provider = :legacy")

# health_score has no source of its own, so it inherits whatever its data source just became.
# Neither Google provider emits scores today, so this is defensive; a row that cannot be
# attributed is left alone rather than guessed at.
_HS_UPDATE_FROM_SOURCE = text("""
    UPDATE health_score hs
    SET provider = ds.provider
    FROM data_source ds
    WHERE ds.id = hs.data_source_id
      AND hs.provider = :legacy
      AND ds.provider IN (:api, :sdk)
""")
# sync_run records the transport that produced it, so an SDK batch logged under the old
# shared slug belongs to Health Connect. Same shape as the data_source rule: claim by the
# discriminator first, then the catch-all.
_SR_SDK_UPDATE = text("UPDATE sync_run SET provider = :sdk WHERE provider = :legacy AND source = :sdk_source")
_SR_UPDATE = text("UPDATE sync_run SET provider = :api WHERE provider = :legacy")
_PS_UPDATE = text("UPDATE provider_settings SET provider = :api WHERE provider = :legacy")

# An SDK upload under the old slug left a tokenless connection behind. disconnect() keeps
# provider_user_id and scope, so a revoked OAuth row still reads as OAuth here.
_UC_SDK_UPDATE = text("UPDATE user_connection SET provider = :sdk WHERE provider = :legacy" + _UC_NO_OAUTH)
_UC_UPDATE = text("UPDATE user_connection SET provider = :api WHERE provider = :legacy")

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
    health_score = _rowcount(db, _HS_UPDATE_FROM_SOURCE)
    user_connection_sdk = _rowcount(db, _UC_SDK_UPDATE)
    user_connection_api = _rowcount(db, _UC_UPDATE)
    sync_run = _rowcount(db, _SR_SDK_UPDATE) + _rowcount(db, _SR_UPDATE)

    provider_settings = _rowcount(db, _PS_UPDATE)
    _rowcount(db, _PP_CLONE_FOR_SDK)  # must copy the legacy ranking before it is renamed
    provider_priority = _rowcount(db, _PP_UPDATE)

    result = {
        "data_source_api": data_source_api,
        "data_source_sdk": data_source_sdk,
        "health_score": health_score,
        "user_connection_api": user_connection_api,
        "user_connection_sdk": user_connection_sdk,
        "sync_run": sync_run,
        "provider_settings": provider_settings,
        "provider_priority": provider_priority,
    }
    for table, count in result.items():
        print(f"{table:<20} moved {count} row(s)")

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
