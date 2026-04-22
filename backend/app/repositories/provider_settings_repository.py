from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import ProviderSetting
from app.schemas.auth import LiveSyncMode


class ProviderSettingsRepository:
    """Repository for managing provider settings in database."""

    def get_all(self, db: DbSession) -> dict[str, ProviderSetting]:
        """Get all provider settings keyed by provider name."""
        stmt = select(ProviderSetting)
        return {s.provider: s for s in db.execute(stmt).scalars().all()}

    def upsert(
        self,
        db: DbSession,
        provider: str,
        is_enabled: bool,
        live_sync_mode: LiveSyncMode | None = None,
    ) -> ProviderSetting:
        """Insert or update a provider setting."""

        update_fields: dict = {"is_enabled": is_enabled}
        if live_sync_mode is not None:
            update_fields["live_sync_mode"] = live_sync_mode

        stmt = (
            insert(ProviderSetting)
            .values(provider=provider, is_enabled=is_enabled, live_sync_mode=live_sync_mode)
            .on_conflict_do_update(index_elements=["provider"], set_=update_fields)
            .returning(ProviderSetting)
        )
        setting = db.execute(stmt).scalar_one()
        db.commit()
        return setting

    def ensure_all_providers_exist(
        self,
        db: DbSession,
        providers: list[str],
        default_live_sync_modes: dict[str, LiveSyncMode | None],
    ) -> None:
        """Ensure all providers exist and backfill NULL live_sync_mode values.

        Inserts missing providers with defaults. For existing rows where
        live_sync_mode is NULL and a computed default exists, fills in the value.
        """

        existing = self.get_all(db)

        for provider in providers:
            default_mode = default_live_sync_modes.get(provider)
            if provider not in existing:
                stmt = insert(ProviderSetting).values(
                    provider=provider,
                    is_enabled=True,
                    live_sync_mode=default_mode,
                )
                db.execute(stmt)
            elif existing[provider].live_sync_mode is None and default_mode is not None:
                existing[provider].live_sync_mode = default_mode

        db.commit()

    def bulk_update(self, db: DbSession, updates: dict[str, bool]) -> None:
        """Bulk update is_enabled for multiple providers."""

        for provider, is_enabled in updates.items():
            stmt = (
                insert(ProviderSetting)
                .values(provider=provider, is_enabled=is_enabled)
                .on_conflict_do_update(
                    index_elements=["provider"],
                    set_={"is_enabled": is_enabled},
                )
            )
            db.execute(stmt)

        db.commit()
